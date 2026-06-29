from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..deps import DB, CurrentUser
from ..models.clause import Clause
from ..models.contract import Contract, ContractVersion
from ..schemas.clause import ClauseInfo
from ..services.audit_service import log_audit, version_target_label
from ..services.export_service import build_review_report, build_revised_contract, convert_to_pdf

router = APIRouter(prefix="/api/versions", tags=["versions"])


@router.get("/{vid}/preview", response_model=list[ClauseInfo])
async def version_preview(vid: int, db: DB, user: CurrentUser):
    ver = await db.get(ContractVersion, vid)
    if not ver:
        raise HTTPException(404)
    stmt = select(Clause).where(Clause.version_id == vid).order_by(Clause.id)
    clauses = list((await db.execute(stmt)).scalars().all())
    return [ClauseInfo(
        code=c.code, title=c.title, text=c.text,
        level=c.level, type_tags=c.type_tags or [],
    ) for c in clauses]


@router.post("/{vid}/complete-review")
async def complete_review(vid: int, request: Request, db: DB, user: CurrentUser):
    ver = await db.get(ContractVersion, vid)
    if not ver:
        raise HTTPException(404)
    if ver.status != "待人工复核":
        raise HTTPException(400, "当前状态不允许完成复核")
    ver.status = "复核完成"

    await log_audit(db, user_id=user.id, user_post=user.post, action="finalize",
                    target_type="version", target_id=vid,
                    target_label=await version_target_label(db, vid),
                    ip=request.client.host if request.client else None)
    await db.commit()
    return {"ok": True}


@router.get("/{vid}/export/report")
async def export_report(vid: int, request: Request, db: DB, user: CurrentUser,
                        format: str = Query("docx")):
    ver = await db.get(ContractVersion, vid)
    if not ver:
        raise HTTPException(404)
    contract = await db.get(Contract, ver.contract_id)
    buf = await build_review_report(db, vid)
    await log_audit(db, user_id=user.id, user_post=user.post, action="export_report",
                    target_type="version", target_id=vid,
                    target_label=await version_target_label(db, vid),
                    ip=request.client.host if request.client else None)
    await db.commit()
    if format.lower() == "pdf":
        try:
            buf = convert_to_pdf(buf)
        except RuntimeError as e:
            raise HTTPException(500, str(e))
        filename = f"{contract.name}-审查报告.pdf"
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})
    filename = f"{contract.name}-审查报告.docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/{vid}/export/revised")
async def export_revised(vid: int, request: Request, db: DB, user: CurrentUser,
                         format: str = Query("docx")):
    ver = await db.get(ContractVersion, vid)
    if not ver:
        raise HTTPException(404)
    contract = await db.get(Contract, ver.contract_id)
    buf = await build_revised_contract(db, vid)
    await log_audit(db, user_id=user.id, user_post=user.post, action="export_revised",
                    target_type="version", target_id=vid,
                    target_label=await version_target_label(db, vid),
                    ip=request.client.host if request.client else None)
    await db.commit()
    if format.lower() == "pdf":
        try:
            buf = convert_to_pdf(buf)
        except RuntimeError as e:
            raise HTTPException(500, str(e))
        filename = f"{contract.name}-修订稿.pdf"
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})
    filename = f"{contract.name}-修订稿.docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
