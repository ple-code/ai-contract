from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(64), default="")
    post: Mapped[str] = mapped_column(String(16), default="法务")
    role: Mapped[str] = mapped_column(String(16), default="法务")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserPref(Base):
    __tablename__ = "user_pref"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(unique=True, index=True)
    default_post: Mapped[str | None] = mapped_column(String(16), nullable=True)
    remember_post: Mapped[bool] = mapped_column(Boolean, default=False)
    # 个人关注点（在岗位默认基础上的微调；为空则沿用管理员配置/前端默认）
    personal_focus: Mapped[list | None] = mapped_column(JSON, nullable=True)
