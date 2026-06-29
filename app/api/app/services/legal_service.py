from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.legal import LegalArticle


async def find_articles_by_tags(db: AsyncSession, tags: list[str]) -> list[LegalArticle]:
    if not tags:
        return []
    stmt = select(LegalArticle).where(LegalArticle.tags.overlap(tags))
    result = await db.execute(stmt)
    return list(result.scalars().all())


def format_articles_for_prompt(articles: list[LegalArticle]) -> str:
    if not articles:
        return ""
    parts = ["以下是可能相关的法律条文（你只能引用这些条文，不得杜撰法条号）：\n"]
    for a in articles:
        parts.append(f"《{a.law}》{a.article_no}：{a.content}\n")
    return "\n".join(parts)
