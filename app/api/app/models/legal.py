from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class LegalArticle(Base):
    __tablename__ = "legal_article"

    id: Mapped[int] = mapped_column(primary_key=True)
    law: Mapped[str] = mapped_column(String(64))
    book: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(128), nullable=True)
    article_no: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
