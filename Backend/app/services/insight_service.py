from __future__ import annotations

from pydantic import ValidationError

from app.db.repositories.menu_repository import MenuRepository
from app.db.repositories.user_repository import UserRepository
from app.models.insight import (
    ChatRecommendationRequest,
    ChatRecommendationResponse,
    DailyInsightRequest,
    DailyInsightResponse,
)
from app.models.menu import MenuItem
from app.services.openrouter_service import OpenRouterError, OpenRouterService
from app.services.prompt_builder import build_chat_prompt, build_daily_insight_prompt
from app.services.rag_service import RagService


class InsightService:
    def __init__(
        self,
        user_repo: UserRepository,
        menu_repo: MenuRepository,
        rag_service: RagService,
        openrouter_service: OpenRouterService,
    ) -> None:
        self._user_repo = user_repo
        self._menu_repo = menu_repo
        self._rag_service = rag_service
        self._openrouter = openrouter_service

    async def generate_daily_insight(self, payload: DailyInsightRequest) -> DailyInsightResponse:
        preferences = await self._user_repo.get_preferences(payload.user_id)
        menu_candidates = await self._get_menu_candidates(
            preferred_tags=preferences.pref_tags,
            allergen_tags=preferences.allergen_tags,
            favorite_hall=preferences.favorite_hall,
            meal_slot=payload.meal_slot,
            hall_id=payload.hall_id,
            service_date=None,
            fallback_limit=6,
        )

        chunks = await self._rag_service.hybrid_search(payload.query)
        rag_context = self._rag_service.render_context(chunks)

        system_prompt, user_prompt = build_daily_insight_prompt(
            user_query=payload.query,
            lang=payload.lang,
            preferences=preferences,
            menu_candidates=menu_candidates,
            rag_context=rag_context,
        )
        try:
            raw = await self._openrouter.create_structured_chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=1000,
            )

            validated = DailyInsightResponse.model_validate(raw)
            allowed_ids = {item.id for item in menu_candidates}
            return validated.model_copy(
                update={
                    "recommended_dish_ids": [
                        item_id for item_id in validated.recommended_dish_ids if item_id in allowed_ids
                    ],
                    "avoid_dish_ids": [
                        item_id for item_id in validated.avoid_dish_ids if item_id in allowed_ids
                    ],
                }
            )
        except (OpenRouterError, ValidationError):
            # Upstream model issues (e.g., provider 429/invalid json) should not take down
            # daily insight UX; fallback to deterministic recommendation from candidates.
            return self._build_daily_insight_fallback(payload, menu_candidates)

    async def generate_chat_recommendation(
        self,
        payload: ChatRecommendationRequest,
    ) -> ChatRecommendationResponse:
        preferences = await self._user_repo.get_preferences(payload.user_id)
        menu_candidates = await self._get_menu_candidates(
            preferred_tags=preferences.pref_tags,
            allergen_tags=preferences.allergen_tags,
            favorite_hall=preferences.favorite_hall,
            meal_slot=payload.meal_slot,
            hall_id=payload.hall_id,
            service_date=None,
            fallback_limit=8,
        )

        chunks = await self._rag_service.hybrid_search(payload.message)
        rag_context = self._rag_service.render_context(chunks)

        system_prompt, user_prompt = build_chat_prompt(
            user_message=payload.message,
            lang=payload.lang,
            preferences=preferences,
            menu_candidates=menu_candidates,
            rag_context=rag_context,
        )
        raw = await self._openrouter.create_structured_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=900,
        )

        validated = ChatRecommendationResponse.model_validate(raw)
        allowed_ids = {item.id for item in menu_candidates}
        citations = [f"{chunk.source_type.value}:{chunk.source_id}" for chunk in chunks]

        return validated.model_copy(
            update={
                "recommended_dish_ids": [
                    item_id for item_id in validated.recommended_dish_ids if item_id in allowed_ids
                ],
                "avoid_dish_ids": [
                    item_id for item_id in validated.avoid_dish_ids if item_id in allowed_ids
                ],
                "citations": citations[:5] if not validated.citations else validated.citations[:5],
            }
        )

    async def _get_menu_candidates(
        self,
        preferred_tags,
        allergen_tags,
        favorite_hall,
        meal_slot,
        hall_id,
        service_date,
        fallback_limit: int,
    ) -> list[MenuItem]:
        candidates = await self._menu_repo.list_recommended_menu_items(
            preferred_tags=preferred_tags,
            allergen_tags=allergen_tags,
            favorite_hall=favorite_hall,
            meal_slot=meal_slot,
            hall_id=hall_id,
            service_date=service_date,
            limit=fallback_limit,
        )
        if candidates:
            return candidates

        return await self._menu_repo.list_menu_items(
            meal_slot=meal_slot,
            hall_id=hall_id,
            query=None,
            exclude_allergens=allergen_tags,
        )

    @staticmethod
    def _build_daily_insight_fallback(
        payload: DailyInsightRequest,
        menu_candidates: list[MenuItem],
    ) -> DailyInsightResponse:
        top_item = menu_candidates[0] if menu_candidates else None
        recommended_ids = [top_item.id] if top_item else []
        recommended_slot = payload.meal_slot or (top_item.meal_slot if top_item else None)

        if payload.lang == "zh":
            title = "AI 每日洞察"
            summary = "AI 服务当前繁忙，已基于你的偏好和今日菜单给出稳定推荐。"
        else:
            title = "AI Daily Insight"
            summary = "The AI provider is busy right now, so a stable fallback recommendation is returned."

        return DailyInsightResponse(
            title=title,
            summary=summary,
            recommended_meal_slot=recommended_slot,
            recommended_dish_ids=recommended_ids,
            avoid_dish_ids=[],
            nutrition_focus=[],
            safety_alerts=[],
            confidence=0.45,
        )
