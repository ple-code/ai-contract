from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ContractType(Base):
    __tablename__ = "contract_type"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    detect_keywords: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    field_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    legal_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    supported: Mapped[bool] = mapped_column(default=True)


class Contract(Base):
    __tablename__ = "contract"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    no: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    type_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    type_detected: Mapped[str | None] = mapped_column(String(32), nullable=True)
    type_confirmed: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uploader_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploader_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ContractVersion(Base):
    __tablename__ = "contract_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract.id"), index=True)
    version_no: Mapped[int] = mapped_column(default=1)
    source: Mapped[str] = mapped_column(String(32), default="上传")
    status: Mapped[str] = mapped_column(String(32), default="AI初审中")
    file_uri: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(String(256), default="")
    # 该版本从文件中抽取出的合同编号（模板占位为空时为 None）
    contract_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 合同摘要（上传时一次性提取）：甲方/乙方/签订时间/地点/标的/条款结构/基本信息片段。
    # 用于重复合同识别时的快速比对——避免每次都重新解析库内合同的条款文本。
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    baseline_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    baseline_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
