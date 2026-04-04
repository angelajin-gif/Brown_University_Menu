from __future__ import annotations

import logging
import re

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
from app.models.preferences import UserPreferences
from app.services.openrouter_service import OpenRouterError, OpenRouterService
from app.services.prompt_builder import build_chat_prompt, build_daily_insight_prompt
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)


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
        except (OpenRouterError, ValidationError) as error:
            # Keep provider/model errors in backend logs, but return user-facing fallback insight.
            logger.warning(
                "Daily insight fallback triggered for user_id=%s: %s",
                payload.user_id,
                error,
            )
            return self._build_daily_insight_fallback(payload, menu_candidates, preferences)

    async def generate_chat_recommendation(
        self,
        payload: ChatRecommendationRequest,
    ) -> ChatRecommendationResponse:
        preferences = await self._user_repo.get_preferences(payload.user_id)
        raw_candidates = await self._get_menu_candidates(
            preferred_tags=preferences.pref_tags,
            allergen_tags=preferences.allergen_tags,
            favorite_hall=preferences.favorite_hall,
            meal_slot=payload.meal_slot,
            hall_id=payload.hall_id,
            service_date=None,
            fallback_limit=8,
        )
        favorites = await self._user_repo.get_favorites(payload.user_id)
        favorite_ids = set(favorites.menu_item_ids)

        menu_candidates, top_score = self._build_ranked_chat_candidates(
            items=raw_candidates,
            message=payload.message,
            preferred_meal_slot=payload.meal_slot,
            preferred_hall=payload.hall_id,
            preferred_tag_values=[tag.value for tag in preferences.pref_tags],
            favorite_ids=favorite_ids,
        )

        if not menu_candidates:
            return self._build_chat_no_match_response(payload.lang)

        # Deterministic graceful fallback when query does not have a strong meal-like match.
        if top_score < 18:
            return self._build_chat_soft_match_response(payload.lang, menu_candidates[0])

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
        filtered_recommended_ids = [
            item_id for item_id in validated.recommended_dish_ids if item_id in allowed_ids
        ]
        if not filtered_recommended_ids:
            filtered_recommended_ids = [menu_candidates[0].id]

        citations = [f"{chunk.source_type.value}:{chunk.source_id}" for chunk in chunks]

        return validated.model_copy(
            update={
                "recommended_dish_ids": filtered_recommended_ids,
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
        preferences: UserPreferences,
    ) -> DailyInsightResponse:
        top_item = menu_candidates[0] if menu_candidates else None
        recommended_ids = [top_item.id] if top_item else []
        recommended_slot = payload.meal_slot or (top_item.meal_slot if top_item else None)
        pref_values = [tag.value for tag in preferences.pref_tags]
        allergen_values = [tag.value for tag in preferences.allergen_tags]

        pref_focus = pref_values[:3]
        safety_alerts = []
        if allergen_values:
            if payload.lang == "zh":
                safety_alerts.append(
                    f"已优先规避过敏原：{', '.join(allergen_values[:3])}"
                )
            else:
                safety_alerts.append(
                    f"Allergen safeguards applied: {', '.join(allergen_values[:3])}"
                )

        if payload.lang == "zh":
            title = "AI 每日洞察"
            if top_item:
                dish_name = top_item.name_zh or top_item.name_en
                reason_parts = [
                    f"基于今天可供应菜单，推荐你试试「{dish_name}」。",
                    "这道菜与当前偏好方向更匹配",
                ]
                if pref_values:
                    reason_parts.append(f"（偏好：{', '.join(pref_values[:3])}）")
                if allergen_values:
                    reason_parts.append(f"，并已避开你设置的过敏原限制。")
                else:
                    reason_parts.append("。")
                summary = "".join(reason_parts)
            else:
                summary = "今天暂未找到足够强匹配的单品推荐。你可以调整筛选条件或偏好后再试。"
        else:
            title = "AI Daily Insight"
            if top_item:
                dish_name = top_item.name_en or top_item.name_zh
                reason_parts = [
                    f"From today's available menu, {dish_name} is the best fit right now",
                ]
                if pref_values:
                    reason_parts.append(
                        f" for your current preferences ({', '.join(pref_values[:3])})"
                    )
                if allergen_values:
                    reason_parts.append(" while respecting your allergen settings.")
                else:
                    reason_parts.append(".")
                summary = "".join(reason_parts)
            else:
                summary = (
                    "No strong single-item match was found today. Try adjusting filters or preferences."
                )

        return DailyInsightResponse(
            title=title,
            summary=summary,
            recommended_meal_slot=recommended_slot,
            recommended_dish_ids=recommended_ids,
            avoid_dish_ids=[],
            nutrition_focus=pref_focus,
            safety_alerts=safety_alerts,
            confidence=0.58 if top_item else 0.35,
        )

    @staticmethod
    def _build_ranked_chat_candidates(
        items: list[MenuItem],
        message: str,
        preferred_meal_slot,
        preferred_hall,
        preferred_tag_values: list[str],
        favorite_ids: set[str],
        limit: int = 8,
    ) -> tuple[list[MenuItem], int]:
        same_day_items = InsightService._restrict_to_latest_service_date(items)
        filtered_items = [item for item in same_day_items if InsightService._is_meal_like_item(item)]
        if not filtered_items:
            return [], 0

        tokens = InsightService._extract_query_tokens(message)
        query_lower = message.lower()
        wants_light = any(
            token in query_lower
            for token in ["light", "healthy", "low calorie", "low-calorie", "清淡", "轻食", "低卡", "减脂"]
        )
        wants_seafood = any(
            token in query_lower
            for token in ["seafood", "fish", "salmon", "shrimp", "海鲜", "鱼", "三文鱼", "虾"]
        )
        wants_breakfast = any(
            token in query_lower
            for token in ["breakfast", "早餐", "morning", "brunch"]
        )
        wants_high_protein = any(
            token in query_lower
            for token in ["high protein", "protein", "增肌", "高蛋白", "健身"]
        )

        ranked = []
        for item in filtered_items:
            text = (
                f"{item.name_en} {item.name_zh} {item.station_name or ''} "
                f"{item.external_location_name or ''} {item.meal_name or ''}"
            ).lower()
            score = 0

            if item.id in favorite_ids:
                score += 120
            if preferred_meal_slot and item.meal_slot == preferred_meal_slot:
                score += 25
            if preferred_hall and item.hall_id == preferred_hall:
                score += 12
            score += sum(10 for tag in item.tags if tag.value in preferred_tag_values)
            score += sum(4 for token in tokens if token in text)

            if 180 <= item.calories <= 950:
                score += 5

            if wants_light and ("low-calorie" in [tag.value for tag in item.tags] or item.calories <= 380):
                score += 8
            if wants_seafood and ("fish" in [tag.value for tag in item.allergens] or "shellfish" in [tag.value for tag in item.allergens]):
                score += 10
            if wants_breakfast and item.meal_slot.value == "breakfast":
                score += 10
            if wants_high_protein and ("high-protein" in [tag.value for tag in item.tags] or item.macros.protein >= 18):
                score += 10

            ranked.append((score, item))

        ranked.sort(key=lambda pair: pair[0], reverse=True)
        if not ranked:
            return [], 0

        top_score = int(ranked[0][0])
        return [item for _, item in ranked[:limit]], top_score

    @staticmethod
    def _restrict_to_latest_service_date(items: list[MenuItem]) -> list[MenuItem]:
        dated_items = [item for item in items if item.service_date is not None]
        if not dated_items:
            return items
        latest_date = max(item.service_date for item in dated_items if item.service_date is not None)
        return [item for item in items if item.service_date == latest_date]

    @staticmethod
    def _extract_query_tokens(message: str) -> list[str]:
        raw = re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]{2,}", message.lower())
        deduped: list[str] = []
        seen: set[str] = set()
        for token in raw:
            if token in seen:
                continue
            seen.add(token)
            deduped.append(token)
        return deduped[:12]

    @staticmethod
    def _is_meal_like_item(item: MenuItem) -> bool:
        text = f"{item.name_en} {item.name_zh}".lower()
        station_text = (item.station_name or "").lower()

        if any(token in station_text for token in ["condiment", "accompaniment", "topping", "dressing"]):
            return False

        strong_component_tokens = [
            "mayonnaise",
            "mayo",
            "dressing",
            "vinaigrette",
            "aioli",
            "condiment",
            "topping",
            "garnish",
            "syrup",
            "relish",
            "marinade",
            "ketchup",
            "mustard",
            "配料",
            "调味",
            "酱料",
            "浇头",
            "点缀",
        ]
        if any(token in text for token in strong_component_tokens):
            return False

        meal_keywords = [
            "bowl",
            "sandwich",
            "burger",
            "pizza",
            "pasta",
            "soup",
            "salad",
            "waffle",
            "pancake",
            "omelet",
            "omelette",
            "burrito",
            "taco",
            "french toast",
            "scrambled",
            "stir fry",
            "curry",
            "ramen",
            "noodle",
            "rice",
            "chicken",
            "beef",
            "pork",
            "salmon",
            "tofu",
            "breakfast",
            "早餐",
            "主菜",
            "盖饭",
            "拌饭",
            "三明治",
            "汤",
            "披萨",
            "沙拉",
        ]
        if any(token in text for token in meal_keywords):
            return True

        # Heuristic: keep substantial items even without explicit meal keywords.
        return item.calories >= 180 or item.macros.protein >= 10

    @staticmethod
    def _build_chat_no_match_response(lang: str) -> ChatRecommendationResponse:
        reply = (
            "今天暂时没有找到足够强匹配的主餐推荐。你可以放宽筛选条件，或调整偏好后再试。"
            if lang == "zh"
            else "I couldn't find a strong meal-quality match today. Try relaxing filters or adjusting your preferences."
        )
        return ChatRecommendationResponse(
            reply=reply,
            recommended_dish_ids=[],
            avoid_dish_ids=[],
            citations=[],
        )

    @staticmethod
    def _build_chat_soft_match_response(lang: str, item: MenuItem) -> ChatRecommendationResponse:
        dish_name = item.name_zh if lang == "zh" and item.name_zh else item.name_en
        reply = (
            f"今天没有特别强的完全匹配项。你可以先考虑「{dish_name}」，并告诉我你更在意口味、热量还是蛋白质，我再细化。"
            if lang == "zh"
            else f"There isn't a very strong exact match today. A reasonable meal-first option is {dish_name}. Tell me whether taste, calories, or protein matters most and I can refine further."
        )
        return ChatRecommendationResponse(
            reply=reply,
            recommended_dish_ids=[item.id],
            avoid_dish_ids=[],
            citations=[],
        )
