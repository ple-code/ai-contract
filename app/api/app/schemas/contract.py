from datetime import datetime

from pydantic import BaseModel


class ContractBrief(BaseModel):
    id: int
    name: str
    no: str | None = None
    type_code: str | None = None
    type_name: str | None = None
    status: str | None = None
    version_no: int | None = None
    current_version_no: int | None = None
    current_version_id: int | None = None
    has_baseline: bool = False
    updated_at: datetime | None = None
    uploader_name: str | None = None


class ContractListResponse(BaseModel):
    items: list[ContractBrief]
    total: int
    page: int
    page_size: int


class ContractOption(BaseModel):
    id: int
    name: str
    no: str | None = None
    current_version_no: int | None = None


class ClauseInfo(BaseModel):
    id: int
    code: str
    title: str
    text: str
    level: int = 1
    type_tags: list[str] = []
    locator: dict | None = None


class ContractDetail(BaseModel):
    id: int
    name: str
    no: str | None = None
    type_code: str | None = None
    type_name: str | None = None
    type_detected: str | None = None
    type_confirmed: str | None = None
    uploader_name: str | None = None
    current_version_id: int | None = None
    current_version_no: int | None = None
    version_no: int | None = None
    status: str | None = None
    file_name: str | None = None
    baseline_kind: str | None = None
    baseline_label: str | None = None
    clauses: list[ClauseInfo] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContractTypeInfo(BaseModel):
    code: str
    name: str
    supported: bool


class UploadMeta(BaseModel):
    mode: str = "new"
    target_contract_id: int | None = None


class FieldChangeInfo(BaseModel):
    field: str
    from_value: str = ""
    to_value: str = ""
    change_type: str = "mod"  # mod / add / del
