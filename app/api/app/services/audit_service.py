from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditLog


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
