"""Structure-aware chunking for Japanese (and English) book text.

Japanese has no whitespace word boundaries, so this splits on sentence-
ending punctuation instead of words — a solved, dependency-free way to
avoid cutting a sentence in half, without pulling in a full morphological
tokenizer (MeCab/fugashi) Phase 1 doesn't need.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from assistant.extraction import PageText

TARGET_CHARS = 700
OVERLAP_CHARS = 120

# Splits immediately after a sentence-ending mark (Japanese full-width or
# ASCII half-width), unless it's followed by a closing bracket/quote — a
# closing 」』） stays attached to the sentence it closes rather than
# starting the next chunk with a lone punctuation mark.
_SENTENCE_END = re.compile(r"(?<=[。！？!?])(?![」』）\)])")


@dataclass(frozen=True)
class RawChunk:
    """A chunk of extracted text, not yet embedded — `assistant.ingestion`
    embeds these into `services.book_chunk_service.ChunkDraft` rows."""

    chunk_index: int
    page_number: int
    content: str
    # Carried straight from the source page's PageText.ocr_confidence — a
    # chunk never spans a page boundary, so this is always exactly one
    # page's confidence, not an aggregate.
    ocr_confidence: Optional[float] = None


def chunk_pages(
    pages: List[PageText], *, target_chars: int = TARGET_CHARS, overlap_chars: int = OVERLAP_CHARS
) -> List[RawChunk]:
    """Greedily accumulates sentences into ~`target_chars`-sized chunks,
    carrying the tail of one chunk into the start of the next as overlap.
    A chunk never spans a page boundary (each page's buffer is always
    flushed at the end of that page, even if under `target_chars`), and a
    single sentence longer than `target_chars` is kept whole rather than
    truncated — it simply becomes an over-sized chunk on its own."""
    chunks: List[RawChunk] = []
    chunk_index = 0

    for page in pages:
        sentences = [s.strip() for s in _SENTENCE_END.split(page.text) if s.strip()]
        if not sentences:
            continue

        buffer = ""
        for sentence in sentences:
            if buffer and len(buffer) + len(sentence) > target_chars:
                chunks.append(
                    RawChunk(
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        content=buffer,
                        ocr_confidence=page.ocr_confidence,
                    )
                )
                chunk_index += 1
                buffer = buffer[-overlap_chars:] + sentence
            else:
                buffer += sentence

        if buffer:
            chunks.append(
                RawChunk(
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    content=buffer,
                    ocr_confidence=page.ocr_confidence,
                )
            )
            chunk_index += 1

    return chunks
