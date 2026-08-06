"""AI Dairy Assistant orchestration: retrieval + generation + citation
validation, wrapped in the same `actor`-first, `AppError`-raising shape as
every other controller.

Retrieval never blocks generation: even when no book passages are found
(or none are relevant), the question still goes to Claude, which falls
back to clearly-labelled general knowledge (see the system prompt in
`assistant/generation.py`) rather than a dead-end "not found" message —
the farmer gets a real, useful answer either way, and always knows which
kind they got.

Phase 1 is book-only for the *retrieval* side — `actor` isn't used for any
permission check yet (there's no farm data in scope), but the method
signature takes it from day one so Phase 2 (farm-data-blended answers)
can start calling `has_permission`/`ensure_can_access_farm` here without
an API-breaking change to callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from assistant.citations import Citation, extract_citations
from assistant.embedding import embed_query
from assistant.generation import GenerationError, generate_answer
from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from database.session import get_db_session
from services.book_chunk_service import BookChunkService, RetrievedChunk
from utils.exceptions import AppError

_RETRIEVAL_LIMIT = 4

# Both source books are scanned (not born-digital) and were OCR'd with
# EasyOCR at a measured average confidence around 0.3-0.35 — genuinely
# low, not a rounding margin. Rather than silently presenting an OCR'd
# citation with the same trust as a clean one, any answer that actually
# cites a low-confidence page gets an explicit caveat appended.
_LOW_CONFIDENCE_THRESHOLD = 0.5


class AssistantError(AppError):
    """Raised for any assistant-related failure the mobile app should surface."""


@dataclass(frozen=True)
class AssistantAnswer:
    answer: str
    citations: List[Citation]
    grounded: bool


class AssistantController(BaseController):
    def ask(self, actor: AuthenticatedUser, question: str) -> AssistantAnswer:
        if not question.strip():
            raise AssistantError("Please enter a question.")

        with get_db_session() as session:
            query_embedding = embed_query(question)
            passages = BookChunkService(session).hybrid_search(
                query_embedding, question, limit=_RETRIEVAL_LIMIT
            )

        if not passages:
            self.logger.info("No book passages found (actor_id=%s) — falling back to general knowledge.", actor.id)

        try:
            raw_answer = generate_answer(question, passages)
        except GenerationError as exc:
            raise AssistantError(str(exc)) from exc

        citations = extract_citations(raw_answer, passages)
        self.logger.info(
            "Assistant answered (actor_id=%s, passages=%d, citations=%d).",
            actor.id,
            len(passages),
            len(citations),
        )

        answer = raw_answer
        warning = self._low_confidence_warning(citations, passages)
        if warning:
            answer = f"{raw_answer}\n\n{warning}"

        return AssistantAnswer(answer=answer, citations=citations, grounded=len(citations) > 0)

    @staticmethod
    def _low_confidence_warning(citations: List[Citation], passages: List[RetrievedChunk]) -> str:
        """Both source books were scanned and OCR'd — if any *actually
        cited* page came from a low-confidence OCR pass, say so plainly
        rather than presenting it with the same certainty as clean text.
        Matched by (book_title, page_number) since that's the identity a
        `Citation` and a `RetrievedChunk` share."""
        cited_pages = {(c.book_title, c.page_number) for c in citations}
        low_confidence_pages = sorted(
            {
                p.page_number
                for p in passages
                if (p.book_title, p.page_number) in cited_pages
                and p.ocr_confidence is not None
                and p.ocr_confidence < _LOW_CONFIDENCE_THRESHOLD
            }
        )
        if not low_confidence_pages:
            return ""
        pages_str = ", ".join(str(p) for p in low_confidence_pages)
        return (
            f"⚠️ Page(s) {pages_str} were scanned and machine-read (OCR) with low confidence — "
            "please verify this against the physical book before relying on it."
        )
