"""Lazy-loaded local embedding model.

The model loads on first use, not at import time, so the FastAPI process
itself starts quickly on a memory-constrained host — the first
`/assistant/ask` call (or the ingestion script) pays the one-time load
cost, not every deploy/restart.

`cl-nagoya/ruri-v3-30m` (the configured default) was fine-tuned with a
query/document prefix scheme (verified against its model card): queries
must be prefixed "検索クエリ: " and passages "検索文書: " for retrieval to
work as intended — encoding either without its prefix measurably degrades
match quality, so this is not optional cosmetic formatting.
"""
from __future__ import annotations

from typing import List

from config.settings import settings

_QUERY_PREFIX = "検索クエリ: "
_PASSAGE_PREFIX = "検索文書: "

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # heavy import, deferred with the model itself

        _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    return _model


def embed_query(text: str) -> List[float]:
    """Embed a user's question for similarity search against passages."""
    vector = _get_model().encode(_QUERY_PREFIX + text, normalize_embeddings=True)
    return vector.tolist()


def embed_passages(texts: List[str], *, batch_size: int = 32) -> List[List[float]]:
    """Embed book chunks for storage — used only by the ingestion script."""
    prefixed = [_PASSAGE_PREFIX + text for text in texts]
    vectors = _get_model().encode(prefixed, batch_size=batch_size, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]
