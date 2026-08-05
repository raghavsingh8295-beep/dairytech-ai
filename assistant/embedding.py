"""Lazy-loaded local embedding via a quantized ONNX export of
`cl-nagoya/ruri-v3-30m` — not the full PyTorch/sentence-transformers
stack.

This exists because of a real production incident, not a preference:
loading the model through `sentence_transformers.SentenceTransformer`
(torch backend) measured ~477MB resident memory on first use — Render's
free-tier 512MB container OOM-killed the whole API process the first
time `/assistant/ask` was actually called. Loading the same model
through `onnxruntime` instead measures ~280MB, verified to produce
embeddings within 0.997 cosine similarity of the original fp32 model's
output (int8 quantization barely perturbs them) — see
`scripts/export_embedding_model.py` for how `assistant/models/
ruri-v3-30m-onnx/` was generated, if the model ever needs re-exporting.

The model loads on first use, not at import time, so the FastAPI process
itself starts quickly regardless.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np

_MODEL_DIR = Path(__file__).resolve().parent / "models" / "ruri-v3-30m-onnx"

_QUERY_PREFIX = "検索クエリ: "
_PASSAGE_PREFIX = "検索文書: "

_session = None
_tokenizer = None


def _get_session_and_tokenizer():
    global _session, _tokenizer
    if _session is None:
        import onnxruntime as ort  # heavy-ish import, deferred with the session itself
        from tokenizers import Tokenizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        _session = ort.InferenceSession(
            str(_MODEL_DIR / "model_int8.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
        )
        _tokenizer = Tokenizer.from_file(str(_MODEL_DIR / "tokenizer.json"))
        _tokenizer.enable_padding()
        _tokenizer.enable_truncation(max_length=512)
    return _session, _tokenizer


def _encode(texts: List[str]) -> List[List[float]]:
    session, tokenizer = _get_session_and_tokenizer()
    encodings = tokenizer.encode_batch(texts)
    input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

    hidden_state = session.run(
        ["last_hidden_state"], {"input_ids": input_ids, "attention_mask": attention_mask}
    )[0]

    # Mean pooling over real (non-padding) tokens — matches the model's
    # own `1_Pooling/config.json` (pooling_mode_mean_tokens), then L2
    # normalization so cosine similarity/distance behaves as expected.
    mask = attention_mask[..., None].astype(np.float32)
    pooled = (hidden_state * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
    normalized = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
    return normalized.tolist()


def embed_query(text: str) -> List[float]:
    """Embed a user's question for similarity search against passages."""
    return _encode([_QUERY_PREFIX + text])[0]


def embed_passages(texts: List[str], *, batch_size: int = 32) -> List[List[float]]:
    """Embed book chunks for storage — used only by the ingestion script.
    Batched (rather than one huge tokenizer/ONNX call) so ingesting a
    whole book doesn't spike memory proportionally to its chunk count."""
    prefixed = [_PASSAGE_PREFIX + text for text in texts]
    embeddings: List[List[float]] = []
    for start in range(0, len(prefixed), batch_size):
        embeddings.extend(_encode(prefixed[start : start + batch_size]))
    return embeddings
