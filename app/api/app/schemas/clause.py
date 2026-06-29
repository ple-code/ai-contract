from pydantic import BaseModel


class ClauseInfo(BaseModel):
    code: str
    title: str
    text: str
    level: int
    type_tags: list[str] | None = None


class DecisionUpdate(BaseModel):
    decision: str | None = None


class AnnotateUpdate(BaseModel):
    note: str = ""


class ClauseReviewStateInfo(BaseModel):
    clause_code: str
    decision: str | None = None
    note: str | None = None
    applied: bool = False


class VersionReviewState(BaseModel):
    states: list[ClauseReviewStateInfo]
    stance_locked: bool
