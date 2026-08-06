"""Local-machine-only PDF text extraction (PyMuPDF), with an OCR fallback
(EasyOCR) for scanned/image-only pages.

Never imported by `api/` or anything Render runs — see
`requirements-ingest.txt` for why (PyMuPDF is AGPL/commercial-licensed,
fine for a one-off local script, not a good fit for a networked service).
EasyOCR is likewise local-ingestion-only: it's a real dependency (pulls in
torch), acceptable for a one-off script but not something to add to the
deployed server's footprint.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Below this, a page that returned *some* text from normal extraction is
# still treated as scanned (e.g. just a stray page number or watermark
# survived as embedded text on an otherwise-image page).
_MIN_TEXT_CHARS_BEFORE_OCR = 20

# A page can come back with plenty of *characters* from normal extraction
# and still be garbage: a "searchable PDF" someone ran through a generic
# (non-Japanese-aware) OCR tool before handing it to us measured as low as
# 0-20% real Japanese characters on many pages — long strings of Latin
# letter noise ("FUMED", "cra, eam, so, REE") mixed with fragments of
# correct Japanese, not just missing text. A length check alone doesn't
# catch that; this ratio check does, and re-OCRs the page ourselves
# (EasyOCR, tuned for Japanese) instead of trusting text that merely
# exists but isn't actually the book's content.
#
# 0.5 was chosen empirically against the actual two books, not a
# theoretical default: at 0.3, pages that were still visibly garbled on
# manual inspection ("Rene 31\" pee", "SALON WE よる KN MT") were passing
# as "trustworthy"; 0.5 correctly rejects every one of those while still
# accepting genuinely clean pages (a table-of-contents page measured 0.83).
_MIN_JAPANESE_CHAR_RATIO = 0.5

_OCR_RENDER_DPI = 200

_JAPANESE_RANGES = (
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs (kanji)
)


def _japanese_char_ratio(text: str) -> float:
    """Fraction of non-whitespace characters that are hiragana/katakana/
    kanji — used to tell "real Japanese text" apart from OCR noise that
    happens to contain some, since a raw length check can't."""
    meaningful = [c for c in text if not c.isspace()]
    if not meaningful:
        return 0.0
    japanese = sum(1 for c in meaningful if any(lo <= ord(c) <= hi for lo, hi in _JAPANESE_RANGES))
    return japanese / len(meaningful)

_reader = None


def _get_ocr_reader():
    global _reader
    if _reader is None:
        import easyocr  # heavy (pulls in torch) — deferred, and only reached for scanned pages

        _reader = easyocr.Reader(["ja", "en"], gpu=False)
    return _reader


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-indexed, matching how a human would cite a page
    text: str
    # None for normal (non-OCR) extraction — there's nothing to have low
    # confidence about. Set (0-1) only when this page's text came from OCR,
    # so low-quality scans can be flagged to the user later rather than
    # presented with the same confidence as a clean, born-digital page.
    ocr_confidence: Optional[float] = None


def _ocr_page(page) -> PageText:
    reader = _get_ocr_reader()
    pixmap = page.get_pixmap(dpi=_OCR_RENDER_DPI)
    image_bytes = pixmap.tobytes("png")

    results = reader.readtext(image_bytes, detail=1)
    if not results:
        return PageText(page_number=page.number + 1, text="", ocr_confidence=0.0)

    text = "".join(region_text for _, region_text, _ in results)
    confidences = [confidence for _, _, confidence in results]
    return PageText(page_number=page.number + 1, text=text, ocr_confidence=sum(confidences) / len(confidences))


def extract_pages(pdf_path: Path) -> List[PageText]:
    """Extract text from every page: normal text extraction first, falling
    back to OCR only when that yields (near-)nothing — most books are a
    mix of a few pages with a smidge of embedded text (cover, stray page
    numbers) and the rest fully scanned, so this check runs per-page, not
    once for the whole document."""
    import fitz  # PyMuPDF — imported here, not at module load, so this file

    # stays importable (e.g. for type checking) even where PyMuPDF isn't
    # installed, matching the deliberate local-only dependency split.

    pages: List[PageText] = []
    with fitz.open(pdf_path) as doc:
        total = len(doc)
        start = time.monotonic()
        for index, page in enumerate(doc):
            native_text = page.get_text()
            trustworthy = (
                len(native_text.strip()) >= _MIN_TEXT_CHARS_BEFORE_OCR
                and _japanese_char_ratio(native_text) >= _MIN_JAPANESE_CHAR_RATIO
            )
            if trustworthy:
                pages.append(PageText(page_number=index + 1, text=native_text))
            else:
                pages.append(_ocr_page(page))

            done = index + 1
            elapsed = time.monotonic() - start
            remaining = (elapsed / done) * (total - done)
            logger.info(
                "Page %d/%d done (%.0fs elapsed, ~%.0fs remaining).", done, total, elapsed, remaining
            )
    return pages
