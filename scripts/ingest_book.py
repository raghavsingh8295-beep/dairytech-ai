#!/usr/bin/env python3
"""One-off CLI to ingest a book PDF into the AI Dairy Assistant's index.

Local-machine-only: needs the ingestion-only dependencies from
`requirements-ingest.txt` (PyMuPDF), which are never installed on the
deployed API server. Writes directly to whatever `DATABASE_URL` your local
`.env` points at — point it at the same Neon database the API uses so the
deployed assistant can actually see the ingested book.

Usage:
    python scripts/ingest_book.py --title "書名" data/books/book1.pdf

Re-running against an unchanged file is a no-op (content-hash check); a
changed file gets its whole chunk set re-embedded and replaced.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allows running as `python scripts/ingest_book.py` from the repo root
# without installing this project as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.ingestion import ingest_book  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf_path", type=Path, help="Path to the book PDF")
    parser.add_argument("--title", required=True, help="Book title, exactly as it should appear in citations")
    args = parser.parse_args()

    if not args.pdf_path.exists():
        parser.error(f"File not found: {args.pdf_path}")

    ingest_book(args.pdf_path, args.title)


if __name__ == "__main__":
    main()
