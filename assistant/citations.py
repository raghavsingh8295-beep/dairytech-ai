"""Turns an answer's `[N]` citation markers into verified `Citation`
objects — never trusts Claude's own text for a page number.

A citation's `book_title`/`page_number` always comes from the passage list
the retrieval code already built *before* the generation call — Claude can
reference passage [2], but it can never invent what page [2] is on, because
that value is never parsed out of its free-text answer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from services.book_chunk_service import RetrievedChunk

_CITATION_MARKER = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class Citation:
    book_title: str
    page_number: int


def extract_citations(answer: str, passages: List[RetrievedChunk]) -> List[Citation]:
    """Finds every `[N]` marker in `answer`, keeps only the ones whose N is
    a valid 1-based index into `passages` (Claude was given exactly
    `len(passages)` numbered passages, so any N outside that range is
    either a formatting slip or a fabrication — either way, dropped rather
    than surfaced as a citation), and returns them in first-seen order
    with duplicates removed."""
    citations: List[Citation] = []
    seen_pages: set[tuple[str, int]] = set()

    for match in _CITATION_MARKER.finditer(answer):
        index = int(match.group(1))
        if not (1 <= index <= len(passages)):
            continue
        passage = passages[index - 1]
        key = (passage.book_title, passage.page_number)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        citations.append(Citation(book_title=passage.book_title, page_number=passage.page_number))

    return citations
