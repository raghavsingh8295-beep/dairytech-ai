"""AI Service Layer contract.

This module defines *what* the AI can do, independent of *how*. The UI and
controllers will depend only on `AIServiceInterface`, so the concrete
implementation can start as simple statistical rules and later be swapped
for trained models (or a remote inference API) without touching a single
caller. Each method's real implementation arrives with its corresponding
feature module (Health, Breeding, Dashboard, ...); for now they raise
`NotImplementedError` so the boundary is explicit rather than silently
returning fake data.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import List


@dataclass(frozen=True)
class Recommendation:
    """A single farmer-facing, plain-language recommendation."""

    title: str
    explanation: str
    possible_causes: List[str]
    actions: List[str]
    severity: str  # "info" | "warning" | "critical"


class AIServiceInterface(ABC):
    """Contract for all AI-driven insights in DairyTech AI."""

    @abstractmethod
    def calculate_health_score(self, cow_id: int) -> float:
        """Return a 0-100 composite health score for a cow."""

    @abstractmethod
    def predict_milk_yield(self, cow_id: int, horizon_days: int) -> List[float]:
        """Forecast daily milk yield (liters) for the next `horizon_days`."""

    @abstractmethod
    def detect_disease_risk(self, cow_id: int) -> float:
        """Return a 0-1 probability that the cow is at risk of disease."""

    @abstractmethod
    def detect_abnormal_temperature(self, cow_id: int, as_of: date) -> bool:
        """Flag whether the cow's temperature is outside its healthy range."""

    @abstractmethod
    def predict_pregnancy_success(self, cow_id: int) -> float:
        """Return a 0-1 probability of a successful pregnancy/insemination."""

    @abstractmethod
    def generate_recommendations(self, cow_id: int) -> List[Recommendation]:
        """Produce plain-language recommendations for a cow, e.g. a milk drop alert."""


class AIService(AIServiceInterface):
    """Placeholder implementation — wired up in the AI module.

    Kept concrete (not abstract) so the rest of the app can depend on and
    instantiate `AIService` today; every method fails loudly until the AI
    module replaces its body with a real implementation.
    """

    def calculate_health_score(self, cow_id: int) -> float:
        raise NotImplementedError("Implemented in the AI module.")

    def predict_milk_yield(self, cow_id: int, horizon_days: int) -> List[float]:
        raise NotImplementedError("Implemented in the AI module.")

    def detect_disease_risk(self, cow_id: int) -> float:
        raise NotImplementedError("Implemented in the AI module.")

    def detect_abnormal_temperature(self, cow_id: int, as_of: date) -> bool:
        raise NotImplementedError("Implemented in the AI module.")

    def predict_pregnancy_success(self, cow_id: int) -> float:
        raise NotImplementedError("Implemented in the AI module.")

    def generate_recommendations(self, cow_id: int) -> List[Recommendation]:
        raise NotImplementedError("Implemented in the AI module.")
