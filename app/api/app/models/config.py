from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AppModelConfig(Base):
    __tablename__ = "app_model_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    gateway_base_url: Mapped[str] = mapped_column(Text, default="")
    gateway_token_enc: Mapped[str] = mapped_column(Text, default="")
    default_model: Mapped[str] = mapped_column(String(64), default="")
    sensitive_model: Mapped[str] = mapped_column(String(64), default="")
    # 岗位→关注标签（管理员级，系统配置里维护；进入合同时据此自动定位/高亮）
    post_focus: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
