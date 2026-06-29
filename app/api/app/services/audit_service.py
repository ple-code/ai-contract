from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.audit import AuditLog
from ..models.clause import Clause
from ..models.contract import Contract, ContractVersion
from ..models.user import AppUser

_TYPE_CN = {
    "contract": "合同",
    "version": "版本",
    "clause": "条款",
    "user": "用户",
    "config": "系统配置",
}


def _ver_label(ver_no: int | None) -> str:
    return f"v{ver_no}" if ver_no is not None else ""


async def version_target_label(db: AsyncSession, version_id: int) -> str:
    ver = await db.get(ContractVersion, version_id)
    if not ver:
        return f"未知版本（ID {version_id}）"
    contract = await db.get(Contract, ver.contract_id)
    name = contract.name if contract else f"合同 #{ver.contract_id}"
    return f"{name} · {_ver_label(ver.version_no)}"


async def clause_target_label(db: AsyncSession, version_id: int, code: str) -> str:
    ver = await db.get(ContractVersion, version_id)
    contract = await db.get(Contract, ver.contract_id) if ver else None
    cname = contract.name if contract else (f"合同 #{ver.contract_id}" if ver else "")
    stmt = select(Clause).where(Clause.version_id == version_id, Clause.code == code)
    clause = (await db.execute(stmt)).scalar_one_or_none()
    title = clause.title if clause and clause.title else f"条款 {code}"
    ver_part = _ver_label(ver.version_no) if ver else ""
    if cname and ver_part:
        return f"{cname} · {title} · {ver_part}"
    if cname:
        return f"{cname} · {title}"
    return title


def _needs_resolve(log: AuditLog) -> bool:
    """历史数据或前端兜底格式，需反查补全。"""
    label = (log.target_label or "").strip()
    if not label:
        return True
    t, tid = log.target_type, (log.target_id or "").strip()
    type_cn = _TYPE_CN.get(t or "")
    if type_cn and tid and label == f"{type_cn} · {tid}":
        return True
    if t == "version" and tid and label in (tid, f"v{tid}"):
        return True
    return False


async def resolve_audit_target_label(db: AsyncSession, log: AuditLog) -> str:
    """列表展示用：优先已有 label，弱标签或空值则按 target 反查补全。"""
    if not _needs_resolve(log):
        return log.target_label.strip()  # type: ignore[union-attr]

    t, tid = log.target_type, log.target_id

    if t == "version" and tid:
        try:
            return await version_target_label(db, int(tid))
        except (ValueError, TypeError):
            pass

    if t == "clause" and tid and "/" in tid:
        vid_str, code = tid.split("/", 1)
        try:
            return await clause_target_label(db, int(vid_str), code)
        except (ValueError, TypeError):
            pass

    if t == "contract" and tid:
        try:
            c = await db.get(Contract, int(tid))
            if c:
                return c.name
        except (ValueError, TypeError):
            pass

    if t == "user" and tid:
        try:
            u = await db.get(AppUser, int(tid))
            if u:
                return u.display_name or u.username
        except (ValueError, TypeError):
            pass

    if t == "config":
        return "系统配置"

    type_cn = _TYPE_CN.get(t or "", t or "")
    if type_cn and tid:
        return f"{type_cn} · {tid}"
    return type_cn or tid or "-"


async def batch_resolve_audit_target_labels(db: AsyncSession, logs: list[AuditLog]) -> dict[int, str]:
    """批量解析审计对象描述，避免列表 N+1 查询。"""
    result: dict[int, str] = {}
    need: list[AuditLog] = []
    for log in logs:
        if _needs_resolve(log):
            need.append(log)
        else:
            result[log.id] = (log.target_label or "").strip() or "-"

    if not need:
        return result

    version_ids: set[int] = set()
    clause_keys: set[tuple[int, str]] = set()
    contract_ids: set[int] = set()
    user_ids: set[int] = set()

    for log in need:
        t, tid = log.target_type, log.target_id
        if t == "version" and tid:
            try:
                version_ids.add(int(tid))
            except (ValueError, TypeError):
                pass
        elif t == "clause" and tid and "/" in tid:
            vid_str, code = tid.split("/", 1)
            try:
                clause_keys.add((int(vid_str), code))
                version_ids.add(int(vid_str))
            except (ValueError, TypeError):
                pass
        elif t == "contract" and tid:
            try:
                contract_ids.add(int(tid))
            except (ValueError, TypeError):
                pass
        elif t == "user" and tid:
            try:
                user_ids.add(int(tid))
            except (ValueError, TypeError):
                pass

    versions: dict[int, ContractVersion] = {}
    if version_ids:
        for v in (await db.execute(select(ContractVersion).where(ContractVersion.id.in_(version_ids)))).scalars():
            versions[v.id] = v
            contract_ids.add(v.contract_id)

    contracts: dict[int, Contract] = {}
    if contract_ids:
        for c in (await db.execute(select(Contract).where(Contract.id.in_(contract_ids)))).scalars():
            contracts[c.id] = c

    users: dict[int, AppUser] = {}
    if user_ids:
        for u in (await db.execute(select(AppUser).where(AppUser.id.in_(user_ids)))).scalars():
            users[u.id] = u

    clauses: dict[tuple[int, str], Clause] = {}
    if clause_keys:
        vids = {k[0] for k in clause_keys}
        for cl in (await db.execute(select(Clause).where(Clause.version_id.in_(vids)))).scalars():
            clauses[(cl.version_id, cl.code)] = cl

    def _version_label(vid: int) -> str:
        ver = versions.get(vid)
        if not ver:
            return f"未知版本（ID {vid}）"
        contract = contracts.get(ver.contract_id)
        name = contract.name if contract else f"合同 #{ver.contract_id}"
        return f"{name} · {_ver_label(ver.version_no)}"

    def _clause_label(vid: int, code: str) -> str:
        ver = versions.get(vid)
        contract = contracts.get(ver.contract_id) if ver else None
        cname = contract.name if contract else (f"合同 #{ver.contract_id}" if ver else "")
        clause = clauses.get((vid, code))
        title = clause.title if clause and clause.title else f"条款 {code}"
        ver_part = _ver_label(ver.version_no) if ver else ""
        if cname and ver_part:
            return f"{cname} · {title} · {ver_part}"
        if cname:
            return f"{cname} · {title}"
        return title

    for log in need:
        t, tid = log.target_type, log.target_id
        label = "-"
        if t == "version" and tid:
            try:
                label = _version_label(int(tid))
            except (ValueError, TypeError):
                pass
        elif t == "clause" and tid and "/" in tid:
            vid_str, code = tid.split("/", 1)
            try:
                label = _clause_label(int(vid_str), code)
            except (ValueError, TypeError):
                pass
        elif t == "contract" and tid:
            try:
                c = contracts.get(int(tid))
                label = c.name if c else f"合同 #{tid}"
            except (ValueError, TypeError):
                pass
        elif t == "user" and tid:
            try:
                u = users.get(int(tid))
                label = (u.display_name or u.username) if u else f"用户 #{tid}"
            except (ValueError, TypeError):
                pass
        elif t == "config":
            label = "系统配置"
        else:
            type_cn = _TYPE_CN.get(t or "", t or "")
            label = f"{type_cn} · {tid}" if type_cn and tid else (type_cn or tid or "-")

        result[log.id] = label

    return result


async def log_audit(
    db: AsyncSession,
    *,
    user_id: int | None = None,
    user_post: str | None = None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    target_label: str | None = None,
    ip: str | None = None,
    detail: dict | None = None,
):
    entry = AuditLog(
        user_id=user_id,
        user_post=user_post,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        target_label=target_label,
        ip=ip,
        detail=detail,
    )
    db.add(entry)
    await db.flush()
