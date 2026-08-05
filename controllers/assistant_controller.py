"""AI Dairy Assistant orchestration: retrieval + generation + citation
validation, wrapped in the same `actor`-first, `AppError`-raising shape as
every other controller.

Phase 1 is book-only — `actor` isn't used for any permission check yet
(there's no farm data in scope), but the method signature takes it from
day one so Phase 2 (farm-data-blended answers) can start calling
`has_permission`/`ensure_can_access_farm` here without an API-breaking
change to callers.
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
from services.book_chunk_service import BookChunkService
from utils.exceptions import AppError

_RETRIEVAL_LIMIT = 4

_NO_EVIDENCE_MESSAGE = (
    "I could not find enough information in the uploaded books to answer this reliably.\n"
    "アップロードされた書籍内に、この質問へ確実に回答できる十分な情報が見つかりませんでした。\n"
    "अपलोड की गई किताबों में इस सवाल का पक्का जवाब देने लायक जानकारी नहीं मिली।"
)


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
            self.logger.info("No book passages found for a question (actor_id=%s).", actor.id)
            return AssistantAnswer(answer=_NO_EVIDENCE_MESSAGE, citations=[], grounded=False)

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
        return AssistantAnswer(answer=raw_answer, citations=citations, grounded=len(citations) > 0)
