import json
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.clause import Clause, ClauseReviewState
from ..models.review import Finding, Review
from ..models.contract import ContractVersion
from ..services.legal_service import find_articles_by_tags, format_articles_for_prompt
from ..services.rule_service import find_rules_for_clause, format_rules_for_prompt
from ..services.model_gateway import chat_completion
from ..prompts.review_clause import build_review_prompt, FIELD_EXTRACT_PROMPT


async def is_stance_locked(db: AsyncSession, version_id: int) -> bool:
    stmt = select(ClauseReviewState).where(ClauseReviewState.version_id == version_id)
    states = (await db.execute(stmt)).scalars().all()
    return any(s.decision is not None or (s.note and s.note.strip()) or s.applied for s in states)


STANCES = ("buyer", "seller", "neutral")


async def run_review(
    db: AsyncSession,
    version_id: int,
    user_id: int | None = None,
) -> AsyncIterator[dict]:
    """AI 初审：一次性生成甲方/乙方/中立三个立场的审查结果。

    每个立场各自创建一条 Review（同 version_id，不同 stance），切换立场时
    直接查询返回，不再重新调用模型。进度按 条款数 × 3 累计。
    """
    reviews: dict[str, Review] = {}
    for stance in STANCES:
        review = Review(version_id=version_id, stance=stance, status="running")
        db.add(review)
        await db.flush()
        reviews[stance] = review

    yield {"type": "start", "review_ids": {s: r.id for s, r in reviews.items()}}

    clauses_stmt = select(Clause).where(Clause.version_id == version_id).order_by(Clause.code)
    clauses = list((await db.execute(clauses_stmt)).scalars().all())

    total_units = len(clauses) * len(STANCES)
    yield {"type": "progress", "total": total_units, "completed": 0}

    # 关键字段抽取（三立场共享一次调用）
    full_text = "\n".join(f"【{c.title}】\n{c.text}" for c in clauses if c.text)
    field_summary: dict = {}
    try:
        field_resp = await chat_completion(
            db,
            [{"role": "system", "content": FIELD_EXTRACT_PROMPT},
             {"role": "user", "content": full_text[:8000]}],
            scene="field_extract", user_id=user_id,
        )
        field_content = field_resp["choices"][0]["message"]["content"]
        field_summary = _parse_json(field_content) or {}
        yield {"type": "field_summary", "data": field_summary}
    except Exception:
        pass

    completed = 0
    for clause in clauses:
        if not clause.text or len(clause.text.strip()) < 10:
            completed += len(STANCES)
            continue

        tags = clause.type_tags or []
        articles = await find_articles_by_tags(db, tags)
        legal_context = format_articles_for_prompt(articles)
        # 确定性审查规则：按条款命中关键词注入 prompt（与法律条文并列，防遗漏）
        rules = await find_rules_for_clause(db, clause.title, clause.text)
        rules_context = format_rules_for_prompt(rules)

        for stance in STANCES:
            messages = build_review_prompt(clause.title, clause.text, stance, legal_context, rules_context)
            try:
                resp = await chat_completion(db, messages, scene="clause_review", user_id=user_id)
                content = resp["choices"][0]["message"]["content"]
                parsed = _parse_json(content)
                if parsed:
                    finding = Finding(
                        review_id=reviews[stance].id,
                        clause_code=clause.code,
                        risk_level=parsed.get("risk_level", "low"),
                        finding=parsed.get("finding", ""),
                        suggestion=parsed.get("suggestion", ""),
                        legal_basis=parsed.get("legal_basis"),
                        stance_note=parsed.get("stance_note", ""),
                    )
                    db.add(finding)
                    await db.flush()
                    completed += 1
                    yield {
                        "type": "finding",
                        "stance": stance,
                        "data": {
                            "id": finding.id,
                            "clause_code": clause.code,
                            "clause_title": clause.title,
                            "risk_level": finding.risk_level,
                            "finding": finding.finding,
                            "suggestion": finding.suggestion,
                            "legal_basis": finding.legal_basis,
                            "stance_note": finding.stance_note,
                        },
                        "progress": {"total": total_units, "completed": completed},
                    }
                else:
                    completed += 1
            except Exception as e:
                completed += 1
                yield {"type": "error", "stance": stance, "clause_code": clause.code, "message": str(e)}

    for review in reviews.values():
        review.status = "completed"
        review.model_used = "configured"

    version = await db.get(ContractVersion, version_id)
    if version:
        version.status = "待人工复核"

    await db.commit()

    yield {"type": "complete", "review_ids": {s: r.id for s, r in reviews.items()}, "field_summary": field_summary}


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
    return None
