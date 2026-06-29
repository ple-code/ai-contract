from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.rule import ReviewRule


async def find_rules_for_clause(db: AsyncSession, title: str, text: str) -> list[ReviewRule]:
    """返回所有启用规则中，match_keywords 命中（title+text）的规则，按 id 升序。"""
    stmt = select(ReviewRule).where(ReviewRule.enabled == True).order_by(ReviewRule.id)
    rules = list((await db.execute(stmt)).scalars().all())
    blob = (title + "\n" + text).lower()
    hit: list[ReviewRule] = []
    for r in rules:
        kws = [k.strip() for k in (r.match_keywords or "").split(",") if k.strip()]
        if not kws:
            continue
        if any(k.lower() in blob for k in kws):
            hit.append(r)
    return hit


_RISK_CN = {"high": "高", "medium": "中", "low": "低"}


def format_rules_for_prompt(rules: list[ReviewRule]) -> str:
    """把命中规则拼成 prompt 片段，指示 AI 命中即点名并按 suggestion 处理。"""
    if not rules:
        return ""
    parts = ["此外，请务必按以下确定性审查规则逐条核验本条款（命中即须在 finding 中点名该规则、并按 suggestion 给出修改建议，不得遗漏）："]
    for r in rules:
        parts.append(
            f"- 规则「{r.name}」（{_RISK_CN.get(r.risk_level, r.risk_level)}风险 / 适用类型：{r.rule_type}）："
            f"触发条件：{r.condition_desc}；处理建议：{r.suggestion}"
        )
    return "\n".join(parts)
