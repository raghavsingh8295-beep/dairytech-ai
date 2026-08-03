"""AI insights endpoints: per-cow lactation curve/yield/quality trends,
a Fat:Protein ratio health flag, breeding-window recommendation, and
structured alerts; plus farm-level herd analytics. Mirrors
InsightsController and HerdAnalyticsController exactly."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import CowInsightsOut, FarmDashboardSummaryOut, HerdAnalyticsOut
from api.security import get_current_user
from controllers.auth_controller import AuthenticatedUser
from controllers.herd_analytics_controller import HerdAnalyticsController
from controllers.insights_controller import InsightsController
from utils.exceptions import AppError

router = APIRouter(tags=["insights"])


@router.get("/cows/{cow_id}/insights", response_model=CowInsightsOut)
def get_cow_insights(cow_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> CowInsightsOut:
    try:
        insights = InsightsController().get_cow_insights(current_user, cow_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CowInsightsOut.model_validate(insights)


@router.get("/farms/{farm_id}/analytics", response_model=HerdAnalyticsOut)
def get_farm_analytics(farm_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> HerdAnalyticsOut:
    try:
        analytics = HerdAnalyticsController().get_farm_analytics(current_user, farm_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return HerdAnalyticsOut.model_validate(analytics)


@router.get("/farms/{farm_id}/dashboard", response_model=FarmDashboardSummaryOut)
def get_farm_dashboard(farm_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> FarmDashboardSummaryOut:
    try:
        summary = HerdAnalyticsController().get_dashboard_summary(current_user, farm_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FarmDashboardSummaryOut.model_validate(summary)
