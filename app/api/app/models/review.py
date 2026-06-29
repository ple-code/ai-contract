from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Review(Base):
    __tablename__ = "review"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("contract_version.id"), index=True)
    stance: Mapped[str] = mapped_column(String(16), default="buyer")
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Finding(Base):
    __tablename__ = "finding"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("review.id"), index=True)
    clause_code: Mapped[str] = mapped_column(String(32))
    risk_level: Mapped[str] = mapped_column(String(8), default="mid")
    finding: Mapped[str] = mapped_column(Text, default="")
    suggestion: Mapped[str] = mapped_column(Text, default="")
    legal_basis: Mapped[list | None] = mapped_column(JSON, nullable=True)
    locator: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stance_note: Mapped[str | None] = mapped_column(Text, nullable=True)
