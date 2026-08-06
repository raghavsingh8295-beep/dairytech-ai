"""Book chunk entity — one retrievable passage of a `Book`, with its
embedding vector for semantic search.

No `SoftDeleteMixin` here (unlike most of this app's models): chunks are
cheap to regenerate from the source PDF, and re-ingestion does a
transactional delete-then-reinsert of a book's whole chunk set (see
`assistant/ingestion.py`) rather than editing rows in place — a soft-delete
flag would just be a filter every query has to remember, for no benefit.

`embedding` uses pgvector's `Vector` type, dimension 256 to match
`cl-nagoya/ruri-v3-30m` (the configured `EMBEDDING_MODEL_NAME` default) —
if that model is ever changed to one with a different output dimension,
this column (and any existing embedded rows) must be migrated together.
"""
from __future__ import annotations

from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.book import Book
from models.mixins import TimestampMixin

EMBEDDING_DIMENSIONS = 256


class BookChunk(Base, TimestampMixin):
    __tablename__ = "book_chunks"
    __table_args__ = (UniqueConstraint("book_id", "chunk_index", name="uq_book_chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False)

    # Sequential position within the book (0, 1, 2, ...) — the identity
    # that makes re-ingestion idempotent (uq_book_chunk_index) and gives
    # a stable, human-checkable ordering independent of the DB's own id.
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)

    # Null for normal (non-OCR) extraction. Set (0-1) when this chunk's
    # page was scanned and OCR'd — surfaced as a "verify against the
    # physical book" caveat when a low-confidence chunk is actually cited
    # in an answer (see AssistantController._low_confidence_note).
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    book: Mapped[Book] = relationship("Book", backref="chunks")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BookChunk id={self.id} book_id={self.book_id} page={self.page_number}>"
