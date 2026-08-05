"""Book entity for the AI Dairy Assistant's book-RAG feature.

A `Book` is a reference document (currently the two Japanese dairy-
management books) whose text has been chunked and embedded into
`BookChunk` rows for retrieval. `content_hash` lets re-ingestion detect an
unchanged file and skip re-embedding it (see `assistant/ingestion.py`).
"""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.mixins import SoftDeleteMixin, TimestampMixin


class Book(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 of the source PDF
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Book id={self.id} title={self.title!r}>"
