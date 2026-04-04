from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import HallId, MealSlot


class DailyInsightRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(default="请基于我的偏好给出今天的饮食建议", min_length=1)
    meal_slot: MealSlot | None = None
    hall_id: HallId | None = None
    lang: str = Field(default="zh", pattern=r"^(zh|en)$")
    visible_item_ids: list[str] = Field(default_factory=list, max_length=500)


class DailyInsightResponse(BaseModel):
    title: str
    summary: str
    recommended_meal_slot: MealSlot | None = None
    recommended_dish_ids: list[str] = Field(default_factory=list)
    avoid_dish_ids: list[str] = Field(default_factory=list)
    nutrition_focus: list[str] = Field(default_factory=list)
    safety_alerts: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class ChatConversationContext(BaseModel):
    last_recommended_item_id: str | None = None
    last_ranked_candidate_ids: list[str] = Field(default_factory=list, max_length=20)
    last_interpreted_intent: str | None = None


class ChatRecommendationRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    meal_slot: MealSlot | None = None
    hall_id: HallId | None = None
    lang: str = Field(default="zh", pattern=r"^(zh|en)$")
    visible_item_ids: list[str] = Field(default_factory=list, max_length=500)
    conversation_context: ChatConversationContext | None = None


class ChatRecommendationResponse(BaseModel):
    reply: str
    recommended_dish_ids: list[str] = Field(default_factory=list)
    final_recommended_item_id: str | None = None
    avoid_dish_ids: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    conversation_context: ChatConversationContext | None = None
