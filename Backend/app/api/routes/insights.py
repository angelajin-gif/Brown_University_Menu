from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.api.deps import get_insight_service
from app.models.insight import (
    ChatRecommendationRequest,
    ChatRecommendationResponse,
    DailyInsightRequest,
    DailyInsightResponse,
)
from app.services.insight_service import InsightService
from app.services.openrouter_service import OpenRouterError

router = APIRouter(prefix="/insights", tags=["insights"])


@router.post("/daily", response_model=DailyInsightResponse)
async def create_daily_insight(
    payload: DailyInsightRequest,
    insight_service: InsightService = Depends(get_insight_service),
) -> DailyInsightResponse:
    try:
        return await insight_service.generate_daily_insight(payload)
    except OpenRouterError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"invalid structured output from model: {error}",
        ) from error


@router.post("/chat", response_model=ChatRecommendationResponse)
async def create_chat_recommendation(
    payload: ChatRecommendationRequest,
    insight_service: InsightService = Depends(get_insight_service),
) -> ChatRecommendationResponse:
    try:
        return await insight_service.generate_chat_recommendation(payload)
    except OpenRouterError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"invalid structured output from model: {error}",
        ) from error
