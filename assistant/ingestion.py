"""Orchestrates ingesting one source end-to-end: extract -> chunk -> embed
-> persist. Called only by `scripts/ingest_book.py` — never imported by
`api/`, since PDF extraction depends on the local-only PyMuPDF dependency.

Two entry points share one core pipeline: `ingest_book` (PDF, with OCR
fallback) and `ingest_text` (plain text — e.g. a video transcript the user
already has the rights to — treated as a single "page" since there's no
natural page concept for it).

Deliberately does NOT hold one database session open across the whole
function: extraction+OCR of a scanned book can take the better part of an
hour, and a real incident this session showed why that matters — Neon
kills a connection that sits idle-in-transaction for too long, so a
session opened before that hour of CPU-bound work and only used for
writes at the very end gets silently killed before those writes ever run,
losing the whole hour's work. Each DB touch below opens and closes its
own short-lived session instead.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Optional

from assistant.chunking import chunk_pages
from assistant.embedding import embed_passages
from assistant.extraction import PageText, extract_pages
from database.session import get_db_session
from models.book import Book
from services.book_chunk_service import BookChunkService, ChunkDraft
from services.book_service import BookService
from utils.logger import get_logger

logger = get_logger(__name__)


def _get_existing_book(title: str) -> Optional[Book]:
    with get_db_session() as session:
        book = BookService(session).get_by_title(title)
        if book is not None:
            # Detach the values we need from the session we're about to
            # close — the ORM instance itself shouldn't be used past this
            # point (its session is gone).
            session.expunge(book)
        return book


def _chunk_count_matches(book_id: int, expected: int) -> bool:
    with get_db_session() as session:
        return BookChunkService(session).count_for_book(book_id) == expected


def _persist(title: str, source_filename: str, content_hash: str, drafts: List[ChunkDraft], existing_id: Optional[int]) -> None:
    """The only part of ingestion that touches the database for real work —
    kept to just this fast insert/replace so the session it opens is never
    held open across the slow extraction/OCR/embedding steps above it."""
    with get_db_session() as session:
        book_service = BookService(session)
        chunk_service = BookChunkService(session)

        if existing_id is None:
            book = book_service.create(
                title=title, source_filename=source_filename, content_hash=content_hash, chunk_count=len(drafts)
            )
        else:
            book = book_service.update(
                existing_id, source_filename=source_filename, content_hash=content_hash, chunk_count=len(drafts)
            )

        chunk_service.replace_chunks(book.id, drafts)


def _ingest_pages(title: str, source_filename: str, content_hash: str, pages: List[PageText]) -> None:
    """Shared core: chunk -> embed -> persist, used by both entry points
    below once they've each produced a `List[PageText]` their own way."""
    existing = _get_existing_book(title)
    if existing is not None and existing.content_hash == content_hash and _chunk_count_matches(existing.id, existing.chunk_count):
        logger.info("%r unchanged (hash match, %d chunks already indexed) — skipping.", title, existing.chunk_count)
        return

    raw_chunks = chunk_pages(pages)
    if not raw_chunks:
        raise ValueError(f"No usable text found for {title!r}.")

    logger.info("Embedding %d chunks...", len(raw_chunks))
    embeddings = embed_passages([chunk.content for chunk in raw_chunks])

    drafts = [
        ChunkDraft(
            chunk_index=raw.chunk_index,
            page_number=raw.page_number,
            content=raw.content,
            embedding=embedding,
            ocr_confidence=raw.ocr_confidence,
        )
        for raw, embedding in zip(raw_chunks, embeddings)
    ]

    ocr_confidences = [d.ocr_confidence for d in drafts if d.ocr_confidence is not None]
    if ocr_confidences:
        avg = sum(ocr_confidences) / len(ocr_confidences)
        low = sum(1 for c in ocr_confidences if c < 0.5)
        logger.info(
            "OCR used for %d/%d chunks (avg confidence %.2f, %d below 0.5).", len(ocr_confidences), len(drafts), avg, low
        )

    logger.info("Writing %d chunks to the database...", len(drafts))
    _persist(title, source_filename, content_hash, drafts, existing.id if existing else None)
    logger.info("Ingested %r: %d pages, %d chunks.", title, len(pages), len(drafts))


def ingest_book(pdf_path: Path, title: str) -> None:
    """Idempotent: re-running against an unchanged file (same content hash,
    same chunk count already persisted) is a no-op. A changed file gets its
    entire chunk set atomically replaced — see `BookChunkService.replace_chunks`."""
    content_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    logger.info("Extracting text from %s...", pdf_path)
    pages = extract_pages(pdf_path)
    _ingest_pages(title, pdf_path.name, content_hash, pages)


def ingest_text(text: str, title: str, source_filename: str) -> None:
    """For plain-text sources with no natural page concept (e.g. a video
    transcript) — treated as a single page. Idempotent the same way as
    `ingest_book`, keyed off a hash of the text itself."""
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    _ingest_pages(title, source_filename, content_hash, [PageText(page_number=1, text=text)])
