from pydantic import BaseModel


class LegalArticleInfo(BaseModel):
    id: int
    law: str
    book: str | None = None
    chapter: str | None = None
    article_no: str
    content: str
    tags: list[str] | None = None
