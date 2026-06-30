from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from ..deps import DB, AdminUser, CurrentUser
from ..models.audit import AuditLog
from ..models.config import AppModelConfig
from ..models.user import AppUser
from ..schemas.admin import (
    AuditLogInfo,
    AuditLogListResponse,
    ModelConfigInfo,
    ModelConfigTest,
    ModelConfigUpdate,
    UserBrief,
    UserCreate,
    UserUpdate,
)
from ..security import hash_password
from ..services.audit_service import batch_resolve_audit_target_labels, log_audit
from ..services.model_gateway import decrypt_token, encrypt_token

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/model-config", response_model=ModelConfigInfo)
async def get_model_config(db: DB, user: AdminUser):
    stmt = select(AppModelConfig).limit(1)
    cfg = (await db.execute(stmt)).scalar_one_or_none()
    if not cfg:
        return ModelConfigInfo()
    return ModelConfigInfo(
        gateway_base_url=cfg.gateway_base_url,
        default_model=cfg.default_model,
        sensitive_model=cfg.sensitive_model,
        has_token=bool(cfg.gateway_token_enc),
        post_focus=cfg.post_focus,
    )


@router.put("/model-config")
async def update_model_config(body: ModelConfigUpdate, request: Request, db: DB, user: AdminUser):
    stmt = select(AppModelConfig).limit(1)
    cfg = (await db.execute(stmt)).scalar_one_or_none()
    if not cfg:
        cfg = AppModelConfig()
        db.add(cfg)
    if body.gateway_base_url is not None:
        cfg.gateway_base_url = body.gateway_base_url
    if body.gateway_token is not None:
        cfg.gateway_token_enc = encrypt_token(body.gateway_token) if body.gateway_token else ""
    if body.default_model is not None:
        cfg.default_model = body.default_model
    if body.sensitive_model is not None:
        cfg.sensitive_model = body.sensitive_model
    if body.post_focus is not None:
        cfg.post_focus = body.post_focus
    cfg.updated_by = user.id

    await log_audit(db, user_id=user.id, user_post=user.post, action="config_change",
                    target_type="config", target_label="模型配置",
                    ip=request.client.host if request.client else None)
    await db.commit()
    return {"ok": True}


@router.post("/model-config/test")
async def test_model_config(db: DB, user: AdminUser, body: ModelConfigTest | None = None):
    from ..services.model_gateway import chat_completion
    ov = body or ModelConfigTest()
    try:
        resp = await chat_completion(
            db,
            [{"role": "user", "content": "回复OK"}],
            scene="config_test", user_id=user.id,
            config_override_base_url=ov.gateway_base_url,
            config_override_token=ov.gateway_token,
            config_override_model=ov.default_model,
        )
        content = resp["choices"][0]["message"]["content"]
        return {"ok": True, "response": content, "message": "连通成功"}
    except Exception as e:
        msg = str(e).strip() or type(e).__name__
        return {"ok": False, "error": msg, "message": msg}


@router.get("/users", response_model=list[UserBrief])
async def list_users(db: DB, user: AdminUser, q: str = ""):
    stmt = select(AppUser)
    if q:
        stmt = stmt.where(AppUser.username.ilike(f"%{q}%"))
    stmt = stmt.order_by(AppUser.id)
    users = list((await db.execute(stmt)).scalars().all())
    return [UserBrief(
        id=u.id, username=u.username, display_name=u.display_name,
        post=u.post, role=u.role, enabled=u.enabled, created_at=u.created_at,
    ) for u in users]


@router.post("/users", response_model=UserBrief)
async def create_user(body: UserCreate, request: Request, db: DB, user: AdminUser):
    existing = await db.execute(select(AppUser).where(AppUser.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "用户名已存在")
    new_user = AppUser(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        post=body.post,
        role=body.role,
    )
    db.add(new_user)
    await db.flush()

    await log_audit(db, user_id=user.id, user_post=user.post, action="user_change",
                    target_type="user", target_id=new_user.id, target_label=f"创建用户 {body.username}",
                    ip=request.client.host if request.client else None)
    await db.commit()
    return UserBrief(
        id=new_user.id, username=new_user.username, display_name=new_user.display_name,
        post=new_user.post, role=new_user.role, enabled=new_user.enabled, created_at=new_user.created_at,
    )


@router.put("/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate, request: Request, db: DB, user: AdminUser):
    target = await db.get(AppUser, user_id)
    if not target:
        raise HTTPException(404)
    if body.enabled is not None:
        target.enabled = body.enabled
    if body.password is not None:
        target.password_hash = hash_password(body.password)
    if body.post is not None:
        target.post = body.post
    if body.role is not None:
        target.role = body.role
    if body.display_name is not None:
        target.display_name = body.display_name

    await log_audit(db, user_id=user.id, user_post=user.post, action="user_change",
                    target_type="user", target_id=user_id, target_label=f"修改用户 {target.username}",
                    ip=request.client.host if request.client else None)
    await db.commit()
    return {"ok": True}


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    db: DB, user: AdminUser,
    q: str = "", action: str = "",
    page: int = 1, page_size: int = 20,
):
    base = select(AuditLog)
    if action:
        base = base.where(AuditLog.action == action)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = base.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    logs = list((await db.execute(stmt)).scalars().all())

    user_ids = {l.user_id for l in logs if l.user_id}
    users_map: dict[int, str] = {}
    if user_ids:
        users_stmt = select(AppUser).where(AppUser.id.in_(user_ids))
        for u in (await db.execute(users_stmt)).scalars().all():
            users_map[u.id] = u.display_name or u.username

    labels_map = await batch_resolve_audit_target_labels(db, logs)

    items = []
    for l in logs:
        items.append(AuditLogInfo(
            id=l.id, user_id=l.user_id, user_post=l.user_post,
            username=users_map.get(l.user_id, "") if l.user_id else None,
            action=l.action, target_type=l.target_type,
            target_id=l.target_id, target_label=labels_map.get(l.id, "-"),
            ip=l.ip, detail=l.detail, created_at=l.created_at,
        ))
    return AuditLogListResponse(items=items, total=total, page=page, page_size=page_size)
