from fastapi import APIRouter
from sqlalchemy import select

from ..deps import DB, CurrentUser
from ..models.legal import LegalArticle
from ..schemas.legal import LegalArticleInfo

router = APIRouter(prefix="/api/legal", tags=["legal"])


@router.get("/articles", response_model=list[LegalArticleInfo])
async def list_articles(db: DB, user: CurrentUser, q: str = "", law: str = ""):
    stmt = select(LegalArticle)
    if q:
        stmt = stmt.where(LegalArticle.content.ilike(f"%{q}%"))
    if law:
        stmt = stmt.where(LegalArticle.law == law)
    stmt = stmt.order_by(LegalArticle.id)
    result = await db.execute(stmt)
    return [LegalArticleInfo(
        id=a.id, law=a.law, book=a.book, chapter=a.chapter,
        article_no=a.article_no, content=a.content, tags=a.tags,
    ) for a in result.scalars().all()]


@router.get("/articles/{article_id}", response_model=LegalArticleInfo)
async def get_article(article_id: int, db: DB, user: CurrentUser):
    a = await db.get(LegalArticle, article_id)
    if not a:
        from fastapi import HTTPException
        raise HTTPException(404)
    return LegalArticleInfo(
        id=a.id, law=a.law, book=a.book, chapter=a.chapter,
        article_no=a.article_no, content=a.content, tags=a.tags,
    )
