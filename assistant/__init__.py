"""AI Dairy Assistant — book-RAG retrieval and Claude-backed generation.

`extraction.py` and `ingestion.py` (and the PyMuPDF dependency they need)
are local-machine-only; nothing else in this package should import them
from a path that runs on the deployed API server.
"""
