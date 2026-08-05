"""Orchestrates ingesting one book end-to-end: hash -> extract -> chunk ->
embed -> persist. Called only by `scripts/ingest_book.py` — never imported
by `api/`, since extraction depends on the local-only PyMuPDF dependency.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from assistant.chunking import chunk_pages
from assistant.embedding import embed_passages
from assistant.extraction import extract_pages
from database.session import get_db_session
from services.book_chunk_service import BookChunkService, ChunkDraft
from services.book_service import BookService
from utils.logger import get_logger

logger = get_logger(__name__)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest_book(pdf_path: Path, title: str) -> None:
    """Idempotent: re-running against an unchanged file (same content hash,
    same chunk count already persisted) is a no-op. A changed file gets its
    entire chunk set atomically replaced — see `BookChunkService.replace_chunks`."""
    content_hash = _hash_file(pdf_path)

    with get_db_session() as session:
        book_service = BookService(session)
        chunk_service = BookChunkService(session)
        existing = book_service.get_by_title(title)

        if (
            existing is not None
            and existing.content_hash == content_hash
            and chunk_service.count_for_book(existing.id) == existing.chunk_count
        ):
            logger.info("Book %r unchanged (hash match, %d chunks already indexed) — skipping.", title, existing.chunk_count)
            return

        logger.info("Extracting text from %s...", pdf_path)
        pages = extract_pages(pdf_path)
        raw_chunks = chunk_pages(pages)
        if not raw_chunks:
            raise ValueError(f"No extractable text found in {pdf_path} — is it a scanned/image-only PDF?")

        logger.info("Embedding %d chunks...", len(raw_chunks))
        embeddings = embed_passages([chunk.content for chunk in raw_chunks])

        drafts = [
            ChunkDraft(
                chunk_index=raw.chunk_index,
                page_number=raw.page_number,
                content=raw.content,
                embedding=embedding,
            )
            for raw, embedding in zip(raw_chunks, embeddings)
        ]

        if existing is None:
            book = book_service.create(
                title=title,
                source_filename=pdf_path.name,
                content_hash=content_hash,
                chunk_count=len(drafts),
            )
        else:
            book = book_service.update(
                existing.id,
                source_filename=pdf_path.name,
                content_hash=content_hash,
                chunk_count=len(drafts),
            )

        chunk_service.replace_chunks(book.id, drafts)
        logger.info("Ingested %r: %d pages, %d chunks.", title, len(pages), len(drafts))
