from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class DiffResult(Base):
    __tablename__ = "diff_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("contract_version.id"), index=True)
    baseline_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DiffItem(Base):
    __tablename__ = "diff_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    diff_result_id: Mapped[int] = mapped_column(ForeignKey("diff_result.id"), index=True)
    clause_code: Mapped[str] = mapped_column(String(32))
    change_type: Mapped[str] = mapped_column(String(8))
    old_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    new_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    inline_diff: Mapped[dict | None] = mapped_column(JSON, nullable=True)
