from pydantic import BaseModel


class DiffItemInfo(BaseModel):
    clause_code: str
    change_type: str
    old_title: str | None = None
    new_title: str | None = None
    old_text: str | None = None
    new_text: str | None = None
    inline_diff: dict | None = None


class DiffResultInfo(BaseModel):
    id: int
    version_id: int
    baseline_version_id: int | None = None
    summary: dict | None = None
    items: list[DiffItemInfo]
