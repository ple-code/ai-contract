from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import DB, CurrentUser
from ..models.user import AppUser, UserPref
from ..schemas.auth import LoginRequest, LoginResponse, MeResponse, PrefInfo, PrefUpdate, UserInfo
from ..security import create_access_token, verify_password
from ..services.audit_service import log_audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: DB):
    stmt = select(AppUser).where(AppUser.username == body.username)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    if not user.enabled:
        raise HTTPException(403, "账号已禁用")

    token = create_access_token({"sub": str(user.id)})
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=7 * 24 * 3600)

    await log_audit(db, user_id=user.id, user_post=user.post, action="login",
                    target_type="user", target_id=user.id, ip=request.client.host if request.client else None)
    await db.commit()

    return LoginResponse(
        token=token,
        user=UserInfo(id=user.id, username=user.username, display_name=user.display_name, post=user.post, role=user.role),
    )


@router.post("/logout")
async def logout(response: Response, request: Request, user: CurrentUser, db: DB):
    response.delete_cookie("access_token")
    await log_audit(db, user_id=user.id, user_post=user.post, action="logout",
                    ip=request.client.host if request.client else None)
    await db.commit()
    return {"ok": True}


me_router = APIRouter(prefix="/api/me", tags=["me"])


@me_router.get("", response_model=MeResponse)
async def get_me(user: CurrentUser, db: DB):
    stmt = select(UserPref).where(UserPref.user_id == user.id)
    pref = (await db.execute(stmt)).scalar_one_or_none()
    return MeResponse(
        user=UserInfo(id=user.id, username=user.username, display_name=user.display_name, post=user.post, role=user.role),
        pref=PrefInfo(default_post=pref.default_post if pref else None, remember_post=pref.remember_post if pref else False),
    )


@me_router.put("/pref")
async def update_pref(body: PrefUpdate, user: CurrentUser, db: DB):
    stmt = select(UserPref).where(UserPref.user_id == user.id)
    pref = (await db.execute(stmt)).scalar_one_or_none()
    if not pref:
        pref = UserPref(user_id=user.id)
        db.add(pref)
    if body.default_post is not None:
        pref.default_post = body.default_post
    if body.remember_post is not None:
        pref.remember_post = body.remember_post
    await db.commit()
    return {"ok": True}


class PersonalFocusUpdate(BaseModel):
    personal_focus: list[str] = []


@me_router.get("/personal-focus")
async def get_personal_focus(user: CurrentUser, db: DB):
    """读取当前用户的个人关注点（在岗位默认基础上的个人微调；只影响自己）。"""
    stmt = select(UserPref).where(UserPref.user_id == user.id)
    pref = (await db.execute(stmt)).scalar_one_or_none()
    return {"personal_focus": (pref.personal_focus if pref and pref.personal_focus else [])}


@me_router.put("/personal-focus")
async def update_personal_focus(body: PersonalFocusUpdate, user: CurrentUser, db: DB):
    stmt = select(UserPref).where(UserPref.user_id == user.id)
    pref = (await db.execute(stmt)).scalar_one_or_none()
    if not pref:
        pref = UserPref(user_id=user.id)
        db.add(pref)
    pref.personal_focus = body.personal_focus
    await db.commit()
    return {"ok": True}
