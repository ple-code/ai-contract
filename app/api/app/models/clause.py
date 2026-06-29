from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Clause(Base):
    __tablename__ = "clause"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("contract_version.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(512), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[int] = mapped_column(Integer, default=1)
    type_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    locator: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ClauseReviewState(Base):
    __tablename__ = "clause_review_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("contract_version.id"), index=True)
    clause_code: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_text_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
