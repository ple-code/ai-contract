from pydantic import BaseModel


class ReviewRuleInfo(BaseModel):
    id: int
    name: str
    rule_type: str
    match_keywords: str
    condition_desc: str
    risk_level: str
    suggestion: str
