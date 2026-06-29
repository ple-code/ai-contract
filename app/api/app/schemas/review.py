from pydantic import BaseModel


class ReviewRequest(BaseModel):
    version_id: int
    stance: str = "buyer"


class FindingInfo(BaseModel):
    id: int | None = None
    clause_code: str
    risk_level: str
    finding: str
    suggestion: str
    legal_basis: list[dict] | None = None
    stance_note: str | None = None


class ReviewDetail(BaseModel):
    id: int
    version_id: int
    stance: str
    model_used: str | None = None
    status: str
    findings: list[FindingInfo]
    field_summary: dict | None = None
