"""AI Dairy Assistant endpoint. Mirrors AssistantController exactly — see
that module for the retrieval/generation/citation logic."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import AssistantAskIn, AssistantAskOut
from api.security import get_current_user
from controllers.assistant_controller import AssistantController
from controllers.auth_controller import AuthenticatedUser
from utils.exceptions import AppError

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask", response_model=AssistantAskOut)
def ask_assistant(
    payload: AssistantAskIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> AssistantAskOut:
    try:
        answer = AssistantController().ask(current_user, payload.question)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AssistantAskOut.model_validate(answer)
