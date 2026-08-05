"""Local-machine-only PDF text extraction (PyMuPDF).

Never imported by `api/` or anything Render runs — see
`requirements-ingest.txt` for why (PyMuPDF is AGPL/commercial-licensed,
fine for a one-off local script, not a good fit for a networked service).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-indexed, matching how a human would cite a page
    text: str


def extract_pages(pdf_path: Path) -> List[PageText]:
    """Extract plain text from every page of a born-digital PDF, preserving
    reading order. Phase 1 has no OCR fallback, so a scanned/image-only
    page simply comes back with empty text — the chunker downstream skips
    empty pages rather than treating that as an error."""
    import fitz  # PyMuPDF — imported here, not at module load, so this file

    # stays importable (e.g. for type checking) even where PyMuPDF isn't
    # installed, matching the deliberate local-only dependency split.

    pages: List[PageText] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc):
            pages.append(PageText(page_number=index + 1, text=page.get_text()))
    return pages
