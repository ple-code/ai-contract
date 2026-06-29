from datetime import datetime

from pydantic import BaseModel


class ModelConfigInfo(BaseModel):
    gateway_base_url: str = ""
    default_model: str = ""
    sensitive_model: str = ""
    has_token: bool = False
    post_focus: dict | None = None


class ModelConfigUpdate(BaseModel):
    gateway_base_url: str | None = None
    gateway_token: str | None = None
    default_model: str | None = None
    sensitive_model: str | None = None
    post_focus: dict | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    post: str = "法务"
    role: str = "法务"


class UserUpdate(BaseModel):
    enabled: bool | None = None
    password: str | None = None
    post: str | None = None
    role: str | None = None
    display_name: str | None = None


class UserBrief(BaseModel):
    id: int
    username: str
    display_name: str
    post: str
    role: str
    enabled: bool
    created_at: datetime | None = None


class AuditLogInfo(BaseModel):
    id: int
    user_id: int | None = None
    user_post: str | None = None
    username: str | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    target_label: str | None = None
    ip: str | None = None
    detail: dict | None = None
    created_at: datetime | None = None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogInfo]
    total: int
    page: int
    page_size: int


class ChangeLogInfo(BaseModel):
    id: int
    version_no: int
    event_type: str
    clause_code: str | None = None
    detail: str | None = None
    actor_user_id: int | None = None
    actor_post: str | None = None
    created_at: datetime | None = None
