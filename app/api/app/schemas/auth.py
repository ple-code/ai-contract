from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: "UserInfo"


class UserInfo(BaseModel):
    id: int
    username: str
    display_name: str
    post: str
    role: str


class PrefUpdate(BaseModel):
    default_post: str | None = None
    remember_post: bool | None = None


class PrefInfo(BaseModel):
    default_post: str | None = None
    remember_post: bool = False


class MeResponse(BaseModel):
    user: UserInfo
    pref: PrefInfo
