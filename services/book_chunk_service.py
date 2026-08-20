"""Book chunk persistence and hybrid (vector + keyword) retrieval.

The only file in this app that runs pgvector/pg_trgm SQL directly — every
other retrieval-adjacent module (assistant/) calls through here rather than
building its own queries, matching this app's "services are the only layer
that talks to SQLAlchemy" rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from sqlalchemy import delete, func, select

from models.book import Book
from models.book_chunk import BookChunk
from services.base_service import BaseService

# How many candidates each leg of the hybrid search contributes before
# Reciprocal Rank Fusion narrows them down to the final `limit`. Wider than
# `limit` so a chunk that's merely decent on both legs can outrank one that's
# a lone top hit on only one — RRF needs a real list to rank within.
_CANDIDATES_PER_LEG = 20

# Reciprocal Rank Fusion's smoothing constant — the standard choice from the
# original RRF paper. Not a tunable knob for Phase 1; large enough that the
# difference between rank 1 and rank 2 doesn't dominate the fused score.
_RRF_K = 60


@dataclass(frozen=True)
class ChunkDraft:
    """One chunked-and-embedded passage, ready to persist. Produced by
    `assistant.chunking` + `assistant.embedding`, consumed by
    `replace_chunks` — the shape data takes crossing from the assistant
    package into the persistence layer."""

    chunk_index: int
    page_number: int
    content: str
    embedding: List[float]
    ocr_confidence: Optional[float] = None


@dataclass(frozen=True)
class RetrievedChunk:
    """One hybrid-search hit, with everything `assistant.generation` and
    `assistant.citations` need — the book title and page number are what
    ultimately become a user-facing citation."""

    chunk_id: int
    book_title: str
    page_number: int
    content: str
    ocr_confidence: Optional[float] = None


class BookChunkService(BaseService[BookChunk]):
    model = BookChunk

    def replace_chunks(self, book_id: int, drafts: Sequence[ChunkDraft]) -> None:
        """Delete every existing chunk for `book_id` and insert `drafts` in
        its place, in one transaction — re-ingestion is "the fresh set
        replaces the old one," not an in-place diff, so a book can never
        end up with a mix of stale and current chunks."""
        self.session.execute(delete(BookChunk).where(BookChunk.book_id == book_id))
        for draft in drafts:
            self.session.add(
                BookChunk(
                    book_id=book_id,
                    chunk_index=draft.chunk_index,
                    page_number=draft.page_number,
                    content=draft.content,
                    embedding=draft.embedding,
                    ocr_confidence=draft.ocr_confidence,
                )
            )
        self.session.flush()

    def count_for_book(self, book_id: int) -> int:
        stmt = select(func.count()).select_from(BookChunk).where(BookChunk.book_id == book_id)
        return self.session.execute(stmt).scalar_one()

    def hybrid_search(self, query_embedding: List[float], query_text: str, *, limit: int = 4) -> List[RetrievedChunk]:
        """Vector similarity (pgvector cosine distance) and keyword
        similarity (pg_trgm trigram, character-based rather than
        word-based — Japanese has no whitespace word boundaries, so a
        word-tokenized keyword search like Postgres's default `tsvector`
        config would be far less useful here) are fused with Reciprocal
        Rank Fusion rather than combined by normalizing two differently-
        shaped, differently-scaled distance metrics into one number.

        Both legs (plus the row data needed to build `RetrievedChunk`) are
        fetched in a single round-trip via two CTEs full-outer-joined on
        chunk id, rather than three separate queries — each round-trip to
        Neon carries its own network/connect latency, which measurably
        dominated this method's total time (~5.6s for 3 round-trips vs.
        low-hundreds-of-ms of actual query work)."""
        vector_cte = (
            select(
                BookChunk.id.label("chunk_id"),
                BookChunk.page_number.label("page_number"),
                BookChunk.content.label("content"),
                BookChunk.ocr_confidence.label("ocr_confidence"),
                Book.title.label("book_title"),
                func.row_number().over(order_by=BookChunk.embedding.cosine_distance(query_embedding)).label("rank"),
            )
            .join(Book, Book.id == BookChunk.book_id)
            .where(Book.is_active.is_(True))
            .order_by(BookChunk.embedding.cosine_distance(query_embedding))
            .limit(_CANDIDATES_PER_LEG)
            .cte("vector_candidates")
        )

        keyword_cte = (
            select(
                BookChunk.id.label("chunk_id"),
                BookChunk.page_number.label("page_number"),
                BookChunk.content.label("content"),
                BookChunk.ocr_confidence.label("ocr_confidence"),
                Book.title.label("book_title"),
                func.row_number().over(order_by=func.similarity(BookChunk.content, query_text).desc()).label("rank"),
            )
            .join(Book, Book.id == BookChunk.book_id)
            .where(Book.is_active.is_(True))
            .order_by(func.similarity(BookChunk.content, query_text).desc())
            .limit(_CANDIDATES_PER_LEG)
            .cte("keyword_candidates")
        )

        combined_stmt = (
            select(
                func.coalesce(vector_cte.c.chunk_id, keyword_cte.c.chunk_id).label("chunk_id"),
                func.coalesce(vector_cte.c.book_title, keyword_cte.c.book_title).label("book_title"),
                func.coalesce(vector_cte.c.page_number, keyword_cte.c.page_number).label("page_number"),
                func.coalesce(vector_cte.c.content, keyword_cte.c.content).label("content"),
                func.coalesce(vector_cte.c.ocr_confidence, keyword_cte.c.ocr_confidence).label("ocr_confidence"),
                vector_cte.c.rank.label("vector_rank"),
                keyword_cte.c.rank.label("keyword_rank"),
            )
            .select_from(vector_cte)
            .join(keyword_cte, vector_cte.c.chunk_id == keyword_cte.c.chunk_id, full=True)
        )

        fused_scores: dict[int, float] = {}
        chunk_data: dict[int, RetrievedChunk] = {}
        for row in self.session.execute(combined_stmt):
            score = 0.0
            if row.vector_rank is not None:
                score += 1.0 / (_RRF_K + (row.vector_rank - 1))
            if row.keyword_rank is not None:
                score += 1.0 / (_RRF_K + (row.keyword_rank - 1))
            fused_scores[row.chunk_id] = score
            chunk_data[row.chunk_id] = RetrievedChunk(
                chunk_id=row.chunk_id,
                book_title=row.book_title,
                page_number=row.page_number,
                content=row.content,
                ocr_confidence=row.ocr_confidence,
            )

        top_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)[:limit]
        return [chunk_data[cid] for cid in top_ids]
