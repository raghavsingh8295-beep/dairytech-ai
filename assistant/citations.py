"""The `Citation` type — kept as a stable shape for `AssistantAnswer` and
the API response even though nothing currently populates it: the assistant
answers conversationally now (see `assistant/generation.py`), with no
`[N]`-marker citation parsing. Reintroducing citations later only needs a
producer for this list again, not a schema change up through the mobile
client.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    book_title: str
    page_number: int
