"""AI Dairy Assistant orchestration: retrieval + generation, wrapped in the
same `actor`-first, `AppError`-raising shape as every other controller.

Deliberately thin: the farmer-facing experience is meant to feel like a
normal conversation with Claude, not a citation-heavy research tool — no
source labelling, no confidence caveats, no "grounded" warnings surfaced
to the user (see the system prompt in `assistant/generation.py` for the
full reasoning). This controller's only real jobs are retrieving whatever
background passages might help and handing the question to Claude.

Phase 1 is book-only for the *retrieval* side — `actor` isn't used for any
permission check yet (there's no farm data in scope), but the method
signature takes it from day one so Phase 2 (farm-data-blended answers)
can start calling `has_permission`/`ensure_can_access_farm` here without
an API-breaking change to callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from assistant.citations import Citation
from assistant.embedding import embed_query
from assistant.generation import GenerationError, generate_answer
from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from database.session import get_db_session
from services.book_chunk_service import BookChunkService
from utils.exceptions import AppError

_RETRIEVAL_LIMIT = 4


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

        try:
            answer = generate_answer(question, passages)
        except GenerationError as exc:
            raise AssistantError(str(exc)) from exc

        self.logger.info("Assistant answered (actor_id=%s, passages_used=%d).", actor.id, len(passages))
        return AssistantAnswer(answer=answer, citations=[], grounded=True)
