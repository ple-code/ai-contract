from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import async_session
from .models.user import AppUser
from .security import decode_access_token


async def get_db():
    async with async_session() as session:
        yield session


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(default=None),
) -> AppUser:
    token = access_token
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "未登录")
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(401, "令牌无效或已过期")
    user = await db.get(AppUser, int(payload["sub"]))
    if not user or not user.enabled:
        raise HTTPException(401, "用户不存在或已禁用")
    return user


async def require_admin(user: AppUser = Depends(get_current_user)) -> AppUser:
    if user.role != "管理员":
        raise HTTPException(403, "需要管理员权限")
    return user


DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[AppUser, Depends(get_current_user)]
AdminUser = Annotated[AppUser, Depends(require_admin)]
