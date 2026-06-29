import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..deps import DB, CurrentUser
from ..models.changelog import ChangeLog
from ..models.clause import Clause
from ..models.contract import Contract, ContractType, ContractVersion
from ..models.diff import DiffItem, DiffResult
from ..models.review import Finding, Review
from ..schemas.admin import ChangeLogInfo
from ..schemas.contract import (
    ClauseInfo,
    ContractBrief,
    ContractDetail,
    ContractListResponse,
    ContractOption,
    ContractTypeInfo,
    FieldChangeInfo,
)
from ..schemas.diff import DiffItemInfo, DiffResultInfo
from ..services.audit_service import log_audit
from ..services.field_extractor import summarize_field_changes
from ..services.diff_engine import compute_diff
from ..services.doc_parser import ParsedClause, extract_contract_no, extract_contract_summary
from ..services.parser_registry import get_parser, supported_formats
from ..services.similarity_checker import find_similar_contract
from ..services.type_detector import detect_contract_type

from ..models.config import AppModelConfig

router = APIRouter(prefix="/api", tags=["contracts"])


@router.get("/ai-status")
async def ai_status(db: DB, user: CurrentUser):
    """任何已登录用户可调用：检查 AI 模型是否已配置可用。"""
    stmt = select(AppModelConfig).limit(1)
    cfg = (await db.execute(stmt)).scalar_one_or_none()
    if cfg and cfg.gateway_base_url and cfg.gateway_token_enc:
        return {"ready": True}
    if settings.AI_BASE_URL and settings.AI_API_KEY:
        return {"ready": True}
    return {"ready": False, "message": "AI 模型尚未配置"}


@router.get("/post-focus")
async def get_post_focus(db: DB, user: CurrentUser):
    """任何已登录用户可读：岗位→关注标签（管理员在系统配置维护，进入合同时据此自动定位/高亮）。"""
    stmt = select(AppModelConfig).limit(1)
    cfg = (await db.execute(stmt)).scalar_one_or_none()
    return {"post_focus": (cfg.post_focus if cfg and cfg.post_focus else {})}


@router.get("/contracts", response_model=ContractListResponse)
async def list_contracts(
    db: DB,
    user: CurrentUser,
    q: str = "",
    status: str = "",
    type: str = "",
    page: int = 1,
    page_size: int = 20,
):
    base = select(Contract)
    if q:
        base = base.where(or_(Contract.name.ilike(f"%{q}%"), Contract.no.ilike(f"%{q}%")))
    if type:
        base = base.where(Contract.type_code == type)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = base.order_by(Contract.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    contracts = list((await db.execute(stmt)).scalars().all())

    # 批量预取版本与类型（避免 N+1：远程库网络延迟高，逐行查询会让 20 条列表触发 40+ 次往返）
    version_ids = [c.current_version_id for c in contracts if c.current_version_id]
    versions: dict[int, ContractVersion] = {}
    if version_ids:
        ver_rows = (await db.execute(
            select(ContractVersion).where(ContractVersion.id.in_(version_ids))
        )).scalars().all()
        versions = {v.id: v for v in ver_rows}

    type_codes = {c.type_code for c in contracts if c.type_code}
    type_names: dict[str, str] = {}
    if type_codes:
        ct_rows = (await db.execute(
            select(ContractType).where(ContractType.code.in_(type_codes))
        )).scalars().all()
        type_names = {t.code: t.name for t in ct_rows}

    items = []
    for c in contracts:
        ver = versions.get(c.current_version_id) if c.current_version_id else None
        ver_status = ver.status if ver else None
        ver_no = ver.version_no if ver else None

        if status:
            statuses = [s.strip() for s in status.split(",")]
            if ver_status not in statuses:
                continue

        items.append(ContractBrief(
            id=c.id, name=c.name, no=c.no, type_code=c.type_code,
            type_name=type_names.get(c.type_code) if c.type_code else None,
            status=ver_status, version_no=ver_no, current_version_no=ver_no,
            current_version_id=c.current_version_id,
            has_baseline=bool(ver and ver.baseline_kind),
            updated_at=c.updated_at, uploader_name=c.uploader_name,
        ))

    return ContractListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/contracts/options", response_model=list[ContractOption])
async def contract_options(db: DB, user: CurrentUser, q: str = ""):
    stmt = select(Contract)
    if q:
        stmt = stmt.where(or_(Contract.name.ilike(f"%{q}%"), Contract.no.ilike(f"%{q}%")))
    stmt = stmt.order_by(Contract.updated_at.desc()).limit(20)
    result = await db.execute(stmt)
    items = result.scalars().all()
    cids = [c.id for c in items]
    ver_map: dict[int, int] = {}
    if cids:
        ver_stmt = select(ContractVersion.contract_id, ContractVersion.version_no).where(
            ContractVersion.contract_id.in_(cids)
        )
        for row in (await db.execute(ver_stmt)).all():
            ver_map[row[0]] = max(ver_map.get(row[0], 0), row[1])
    return [ContractOption(id=c.id, name=c.name, no=c.no, current_version_no=ver_map.get(c.id)) for c in items]


@router.get("/contract-types", response_model=list[ContractTypeInfo])
async def list_contract_types(db: DB):
    result = await db.execute(select(ContractType))
    return [ContractTypeInfo(code=t.code, name=t.name, supported=t.supported) for t in result.scalars().all()]


@router.post("/contracts")
async def create_contract(
    request: Request,
    db: DB,
    user: CurrentUser,
    file: UploadFile = File(...),
    mode: str = Form("new"),
    target_contract_id: int | None = Form(None),
    contract_name: str = Form(""),
    confirm_duplicate: bool = Form(False),
):
    if not file.filename:
        raise HTTPException(400, "未上传文件")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    parser = get_parser(ext)
    if not parser:
        fmts = ", ".join(f".{f}" for f in supported_formats())
        raise HTTPException(422, f"暂不支持 .{ext} 格式，当前支持: {fmts}")

    file_id = uuid.uuid4().hex
    save_path = settings.upload_path / f"{file_id}.{ext}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    clauses = parser.parse(str(save_path))
    full_text = "\n".join(c.title + " " + c.text for c in clauses)
    type_code, confidence = detect_contract_type(full_text)

    if type_code == "unknown":
        supported = await db.execute(select(ContractType).where(ContractType.supported == True))
        supported_types = [t.name for t in supported.scalars().all()]
        return {
            "ok": False,
            "error": "unsupported_type",
            "message": "暂无法识别合同类型或暂不支持该类型",
            "supported_types": supported_types,
            "detected_type": None,
            "file_id": file_id,
        }

    name = contract_name or file.filename or "未命名合同"
    # 抽取合同编号（模板占位为空 → None；真实合同如 CG-2026-0627）
    contract_no = extract_contract_no(full_text)
    # 抽取合同摘要（甲方/乙方/时间/地点/条款结构等），存到 version.summary，
    # 供重复合同识别时做快速比对（避免每次重新解析库内合同）。
    summary = extract_contract_summary(clauses, contract_no=contract_no)

    # 重复合同识别（仅 mode=new 且未经用户确认时）：
    #   1) 合同编号确定性匹配 —— 编号字符串相等直接判定撞号；
    #   2) AI 语义相似度 —— 编号为空 / 未撞号但合同内容雷同（同交易的不同版本）。
    # 任一命中即返回 duplicate_detected，前端弹确认框（关联为新版本 / 仍作为新合同）。
    # confirm_duplicate=True 表示用户已确认按新合同处理，跳过两级检查。
    if mode == "new" and not confirm_duplicate:
        matched = None  # {id, name, no, current_version_no}
        method = None   # "contract_no" | "ai_similarity"

        # 1) 编号确定性匹配
        if contract_no:
            dup_stmt = select(Contract).where(Contract.no == contract_no).limit(1)
            dup_contract = (await db.execute(dup_stmt)).scalar_one_or_none()
            if dup_contract:
                cur_ver = (
                    await db.get(ContractVersion, dup_contract.current_version_id)
                    if dup_contract.current_version_id else None
                )
                matched = {
                    "id": dup_contract.id,
                    "name": dup_contract.name,
                    "no": dup_contract.no,
                    "current_version_no": cur_ver.version_no if cur_ver else None,
                }
                method = "contract_no"

        # 2) 编号没撞 → AI 语义相似度判断（只比已存储的合同摘要，不重新解析）
        if not matched:
            ai_hit = await find_similar_contract(
                db,
                new_summary=summary, new_name=name, type_code=type_code,
                user_id=user.id,
            )
            if ai_hit:
                matched = {
                    "id": ai_hit["id"],
                    "name": ai_hit["name"],
                    "no": ai_hit["no"],
                    "current_version_no": ai_hit["current_version_no"],
                }
                method = "ai_similarity"

        if matched:
            if method == "contract_no":
                msg = f"检测到合同编号 {contract_no} 与库内已有合同一致"
            else:
                score = ai_hit.get("score") if ai_hit else None
                reason = (ai_hit.get("reason") if ai_hit else "") or ""
                msg = f"AI 判断与「{matched['name']}」可能是同一交易的不同版本"
                if score is not None:
                    msg += f"（相似度 {score}%）"
                if reason:
                    msg += f"：{reason}"
            return {
                "ok": False,
                "error": "duplicate_detected",
                "method": method,
                "message": msg,
                "match": matched,
                "parsed_contract_no": contract_no,
                "type_detected": type_code,
                "file_id": file_id,
            }

    if mode == "version":
        if not target_contract_id:
            raise HTTPException(400, "选择「已有合同的新版本」时必须指定目标合同，请回到上一步选择要关联的合同")
        contract = await db.get(Contract, target_contract_id)
        if not contract:
            raise HTTPException(404, "目标合同不存在")
        max_ver_stmt = select(func.max(ContractVersion.version_no)).where(
            ContractVersion.contract_id == contract.id)
        max_ver = (await db.execute(max_ver_stmt)).scalar() or 0
        ver_no = max_ver + 1
    else:
        contract = Contract(
            name=name, no=contract_no, type_code=type_code, type_detected=type_code,
            uploader_id=user.id, uploader_name=user.display_name or user.username,
        )
        db.add(contract)
        await db.flush()
        ver_no = 1

    version = ContractVersion(
        contract_id=contract.id, version_no=ver_no,
        source="上传", status="AI初审中",
        file_uri=str(save_path), file_name=file.filename or "",
        contract_no=contract_no,
        summary=summary,
        created_by=user.id,
    )
    if mode == "version" and target_contract_id:
        prev_ver = await db.get(ContractVersion, contract.current_version_id) if contract.current_version_id else None
        if prev_ver:
            version.baseline_kind = "上一版本"
            version.baseline_version_id = prev_ver.id
            version.baseline_label = f"v{prev_ver.version_no}"

    db.add(version)
    await db.flush()

    contract.current_version_id = version.id
    contract.type_confirmed = type_code
    # 合同编号以最新版本为主（每传一个新版本都覆盖；新版本没编号则为空）
    contract.no = contract_no

    for c in clauses:
        db.add(Clause(
            version_id=version.id, code=c.code, title=c.title,
            text=c.text, level=c.level, type_tags=c.type_tags,
        ))

    cl = ChangeLog(
        contract_id=contract.id, version_no=ver_no,
        event_type="upload", detail=f"上传 {file.filename}",
        actor_user_id=user.id, actor_post=user.post,
    )
    db.add(cl)

    await log_audit(db, user_id=user.id, user_post=user.post, action="upload",
                    target_type="contract", target_id=contract.id, target_label=name,
                    ip=request.client.host if request.client else None)

    if version.baseline_version_id:
        baseline_clauses_stmt = select(Clause).where(Clause.version_id == version.baseline_version_id)
        baseline_clauses = list((await db.execute(baseline_clauses_stmt)).scalars().all())
        baseline_parsed = [ParsedClause(code=c.code, title=c.title, text=c.text, level=c.level, type_tags=c.type_tags or []) for c in baseline_clauses]
        current_parsed = clauses
        changes = compute_diff(baseline_parsed, current_parsed)

        diff_result = DiffResult(version_id=version.id, baseline_version_id=version.baseline_version_id, summary={})
        db.add(diff_result)
        await db.flush()

        for ch in changes:
            db.add(DiffItem(
                diff_result_id=diff_result.id, clause_code=ch.clause_code,
                change_type=ch.change_type, old_text=ch.old_text, new_text=ch.new_text,
                old_title=ch.old_title, new_title=ch.new_title,
                inline_diff={"html": ch.inline_diff_html} if ch.inline_diff_html else None,
            ))

        db.add(ChangeLog(
            contract_id=contract.id, version_no=ver_no,
            event_type="diff", detail=f"与 v{version.baseline_label or ''} 比对完成，{len(changes)} 处变更",
            actor_user_id=user.id, actor_post=user.post,
        ))

    await db.commit()

    return {
        "ok": True,
        "contract_id": contract.id,
        "version_id": version.id,
        "type_detected": type_code,
        "confidence": confidence,
        "clause_count": len(clauses),
    }


@router.get("/contracts/{contract_id}", response_model=ContractDetail)
async def get_contract(contract_id: int, db: DB, user: CurrentUser):
    contract = await db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, "合同不存在")

    ver = await db.get(ContractVersion, contract.current_version_id) if contract.current_version_id else None

    type_name = None
    if contract.type_code:
        ct_stmt = select(ContractType).where(ContractType.code == contract.type_code)
        ct = (await db.execute(ct_stmt)).scalar_one_or_none()
        type_name = ct.name if ct else None

    clauses: list[ClauseInfo] = []
    if ver:
        cl_stmt = select(Clause).where(Clause.version_id == ver.id).order_by(Clause.id)
        for c in (await db.execute(cl_stmt)).scalars().all():
            clauses.append(ClauseInfo(
                id=c.id, code=c.code, title=c.title, text=c.text,
                level=c.level, type_tags=c.type_tags or [],
            ))

    return ContractDetail(
        id=contract.id, name=contract.name, no=contract.no,
        type_code=contract.type_code, type_name=type_name,
        type_detected=contract.type_detected, type_confirmed=contract.type_confirmed,
        uploader_name=contract.uploader_name,
        current_version_id=contract.current_version_id,
        current_version_no=ver.version_no if ver else None,
        version_no=ver.version_no if ver else None,
        status=ver.status if ver else None,
        file_name=ver.file_name if ver else None,
        baseline_kind=ver.baseline_kind if ver else None,
        baseline_label=ver.baseline_label if ver else None,
        clauses=clauses,
        created_at=contract.created_at, updated_at=contract.updated_at,
    )


@router.get("/contracts/{contract_id}/download")
async def download_original(contract_id: int, db: DB, user: CurrentUser):
    """下载用户最初上传的原文件（当前版本存档的 file_uri，非修订版导出）。"""
    contract = await db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, "合同不存在")
    ver = (await db.get(ContractVersion, contract.current_version_id)
           if contract.current_version_id else None)
    if not ver or not ver.file_uri:
        raise HTTPException(404, "该合同没有可下载的原文件")
    path = Path(ver.file_uri)
    if not path.exists():
        raise HTTPException(404, "原文件已从存储中丢失")
    return FileResponse(path, filename=ver.file_name or path.name)


@router.get("/contracts/{contract_id}/versions/{version_no}/download-source")
async def download_version_source(contract_id: int, version_no: int, db: DB, user: CurrentUser):
    """下载指定版本的原始上传文件（变更记录里每个版本可下载存档原文件）。"""
    stmt = select(ContractVersion).where(
        ContractVersion.contract_id == contract_id,
        ContractVersion.version_no == version_no,
    )
    ver = (await db.execute(stmt)).scalar_one_or_none()
    if not ver or not ver.file_uri:
        raise HTTPException(404, "该版本没有可下载的原文件")
    path = Path(ver.file_uri)
    if not path.exists():
        raise HTTPException(404, "原文件已从存储中丢失")
    return FileResponse(path, filename=ver.file_name or path.name)
async def compare_contract(contract_id: int, db: DB, user: CurrentUser):
    contract = await db.get(Contract, contract_id)
    if not contract or not contract.current_version_id:
        raise HTTPException(404)

    ver = await db.get(ContractVersion, contract.current_version_id)
    if not ver or not ver.baseline_version_id:
        raise HTTPException(400, "当前版本无比对基准")

    diff_stmt = select(DiffResult).where(
        DiffResult.version_id == ver.id,
        DiffResult.baseline_version_id == ver.baseline_version_id,
    )
    diff_result = (await db.execute(diff_stmt)).scalar_one_or_none()
    if not diff_result:
        raise HTTPException(404, "比对结果不存在")

    items_stmt = select(DiffItem).where(DiffItem.diff_result_id == diff_result.id)
    items = list((await db.execute(items_stmt)).scalars().all())

    return DiffResultInfo(
        id=diff_result.id, version_id=diff_result.version_id,
        baseline_version_id=diff_result.baseline_version_id,
        summary=diff_result.summary,
        items=[DiffItemInfo(
            clause_code=i.clause_code, change_type=i.change_type,
            old_title=i.old_title, new_title=i.new_title,
            old_text=i.old_text, new_text=i.new_text,
            inline_diff=i.inline_diff,
        ) for i in items],
    )


@router.get("/contracts/{contract_id}/field-summary", response_model=list[FieldChangeInfo])
async def get_field_summary(contract_id: int, db: DB, user: CurrentUser):
    """关键字段变更摘要：基准 → 当前版本的核心字段级 from→to。

    无比对基准（首次上传）时返回空列表；前端据此隐藏「关键字段变更摘要」区。
    """
    contract = await db.get(Contract, contract_id)
    if not contract or not contract.current_version_id:
        return []

    ver = await db.get(ContractVersion, contract.current_version_id)
    if not ver or not ver.baseline_version_id:
        return []

    diff_stmt = select(DiffResult).where(
        DiffResult.version_id == ver.id,
        DiffResult.baseline_version_id == ver.baseline_version_id,
    )
    diff_result = (await db.execute(diff_stmt)).scalar_one_or_none()
    if not diff_result:
        return []

    items_stmt = select(DiffItem).where(DiffItem.diff_result_id == diff_result.id)
    diff_items = [
        {
            "clause_code": i.clause_code,
            "change_type": i.change_type,
            "old_text": i.old_text,
            "new_text": i.new_text,
        }
        for i in (await db.execute(items_stmt)).scalars().all()
    ]

    clause_stmt = select(Clause).where(Clause.version_id == ver.id)
    current_clauses = [
        {"code": c.code, "type_tags": c.type_tags or []}
        for c in (await db.execute(clause_stmt)).scalars().all()
    ]

    changes = summarize_field_changes(diff_items, current_clauses)
    return [FieldChangeInfo(
        field=ch.field, from_value=ch.from_value,
        to_value=ch.to_value, change_type=ch.change_type,
    ) for ch in changes]


@router.get("/contracts/{contract_id}/change-logs", response_model=list[ChangeLogInfo])
async def get_change_logs(contract_id: int, db: DB, user: CurrentUser, page: int = 1, page_size: int = 50):
    stmt = (select(ChangeLog)
            .where(ChangeLog.contract_id == contract_id)
            .order_by(ChangeLog.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size))
    logs = list((await db.execute(stmt)).scalars().all())
    return [ChangeLogInfo(
        id=l.id, version_no=l.version_no, event_type=l.event_type,
        clause_code=l.clause_code, detail=l.detail,
        actor_user_id=l.actor_user_id, actor_post=l.actor_post,
        created_at=l.created_at,
    ) for l in logs]
