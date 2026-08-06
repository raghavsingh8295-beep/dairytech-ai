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
        shaped, differently-scaled distance metrics into one number."""
        vector_stmt = (
            select(BookChunk.id)
            .join(Book, Book.id == BookChunk.book_id)
            .where(Book.is_active.is_(True))
            .order_by(BookChunk.embedding.cosine_distance(query_embedding))
            .limit(_CANDIDATES_PER_LEG)
        )
        vector_ids = list(self.session.execute(vector_stmt).scalars().all())

        keyword_stmt = (
            select(BookChunk.id)
            .join(Book, Book.id == BookChunk.book_id)
            .where(Book.is_active.is_(True))
            .order_by(func.similarity(BookChunk.content, query_text).desc())
            .limit(_CANDIDATES_PER_LEG)
        )
        keyword_ids = list(self.session.execute(keyword_stmt).scalars().all())

        fused_scores: dict[int, float] = {}
        for rank, chunk_id in enumerate(vector_ids):
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank)
        for rank, chunk_id in enumerate(keyword_ids):
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank)

        if not fused_scores:
            return []

        top_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)[:limit]

        rows = (
            self.session.execute(
                select(BookChunk, Book.title)
                .join(Book, Book.id == BookChunk.book_id)
                .where(BookChunk.id.in_(top_ids))
            )
        ).all()
        by_id = {chunk.id: (chunk, title) for chunk, title in rows}

        # Re-apply the fused ranking — the `IN (...)` query above doesn't
        # preserve `top_ids`' order.
        results = []
        for chunk_id in top_ids:
            if chunk_id not in by_id:
                continue
            chunk, title = by_id[chunk_id]
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    book_title=title,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    ocr_confidence=chunk.ocr_confidence,
                )
            )
        return results
