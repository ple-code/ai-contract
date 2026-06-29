from fastapi import APIRouter, Query
from sqlalchemy import select

from ..deps import DB, CurrentUser
from ..models.rule import ReviewRule
from ..schemas.rule import ReviewRuleInfo

router = APIRouter(prefix="/api/review-rules", tags=["review-rules"])


@router.get("", response_model=list[ReviewRuleInfo])
async def list_rules(
    db: DB, user: CurrentUser,
    level: str = Query("", description="high/medium/low"),
    rule_type: str = Query(""),
    search: str = Query(""),
):
    """审查规则列表（只返回 enabled=true）。供「审查规则」页与 AI 初审共用。"""
    stmt = select(ReviewRule).where(ReviewRule.enabled == True)
    if level:
        stmt = stmt.where(ReviewRule.risk_level == level)
    if rule_type:
        stmt = stmt.where(ReviewRule.rule_type == rule_type)
    stmt = stmt.order_by(ReviewRule.id)
    rows = list((await db.execute(stmt)).scalars().all())
    kw = search.strip().lower()
    if kw:
        rows = [r for r in rows if kw in (r.name + r.condition_desc + r.suggestion + r.match_keywords).lower()]
    return [ReviewRuleInfo(
        id=r.id, name=r.name, rule_type=r.rule_type, match_keywords=r.match_keywords,
        condition_desc=r.condition_desc, risk_level=r.risk_level, suggestion=r.suggestion,
    ) for r in rows]
