from __future__ import annotations

import logging
import re

from pydantic import ValidationError

from app.db.repositories.menu_repository import MenuRepository
from app.db.repositories.user_repository import UserRepository
from app.models.insight import (
    ChatConversationContext,
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
        if payload.visible_item_ids:
            raw_candidates = await self._menu_repo.list_menu_items_by_ids(payload.visible_item_ids)
            excluded_allergen_values = {tag.value for tag in preferences.allergen_tags}
            if excluded_allergen_values:
                raw_candidates = [
                    item
                    for item in raw_candidates
                    if not any(allergen.value in excluded_allergen_values for allergen in item.allergens)
                ]
        else:
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
        menu_candidates, _, _ranking_debug = self._build_ranked_chat_candidates(
            items=raw_candidates,
            message=payload.query,
            preferred_meal_slot=payload.meal_slot,
            preferred_hall=payload.hall_id,
            preferred_tag_values=[tag.value for tag in preferences.pref_tags],
            favorite_ids=favorite_ids,
            limit=6,
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
            filtered_recommended_ids = [
                item_id for item_id in validated.recommended_dish_ids if item_id in allowed_ids
            ]
            if not filtered_recommended_ids and menu_candidates:
                filtered_recommended_ids = [menu_candidates[0].id]
            return validated.model_copy(
                update={
                    "recommended_dish_ids": filtered_recommended_ids,
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
        requested_visible_ids_count = len(payload.visible_item_ids)
        raw_candidates_total = 0
        if payload.visible_item_ids:
            raw_candidates = await self._menu_repo.list_menu_items_by_ids(payload.visible_item_ids)
            raw_candidates_total = len(raw_candidates)
            logger.info(
                "chat_reco_debug user_id=%s stage=visible_restriction requested_visible_ids=%d candidates=%d",
                payload.user_id,
                requested_visible_ids_count,
                raw_candidates_total,
            )
            excluded_allergen_values = {tag.value for tag in preferences.allergen_tags}
            if excluded_allergen_values:
                raw_candidates = [
                    item
                    for item in raw_candidates
                    if not any(allergen.value in excluded_allergen_values for allergen in item.allergens)
                ]
            logger.info(
                "chat_reco_debug user_id=%s stage=allergen_filter excluded=%s candidates=%d",
                payload.user_id,
                sorted(excluded_allergen_values),
                len(raw_candidates),
            )
        else:
            raw_candidates = await self._get_menu_candidates(
                preferred_tags=preferences.pref_tags,
                allergen_tags=preferences.allergen_tags,
                favorite_hall=preferences.favorite_hall,
                meal_slot=payload.meal_slot,
                hall_id=payload.hall_id,
                service_date=None,
                fallback_limit=8,
            )
            raw_candidates_total = len(raw_candidates)
            logger.info(
                "chat_reco_debug user_id=%s stage=visible_restriction requested_visible_ids=0 candidates=%d",
                payload.user_id,
                raw_candidates_total,
            )
            logger.info(
                "chat_reco_debug user_id=%s stage=allergen_filter excluded=%s candidates=%d source=menu_query",
                payload.user_id,
                sorted({tag.value for tag in preferences.allergen_tags}),
                len(raw_candidates),
            )
        favorites = await self._user_repo.get_favorites(payload.user_id)
        favorite_ids = set(favorites.menu_item_ids)

        menu_candidates, top_score, ranking_debug = self._build_ranked_chat_candidates(
            items=raw_candidates,
            message=payload.message,
            preferred_meal_slot=payload.meal_slot,
            preferred_hall=payload.hall_id,
            preferred_tag_values=[tag.value for tag in preferences.pref_tags],
            favorite_ids=favorite_ids,
        )
        logger.info(
            "chat_reco_debug user_id=%s stage=ranking total_raw_candidates=%d after_visible_restriction=%d "
            "after_allergen_filter=%d after_meal_like_filter=%d after_latest_service_date=%d "
            "latest_service_fallback_used=%s preference_ranking_pool=%d preference_signal_items=%d "
            "favorites_in_pool=%d ranked_candidates=%d top_ranked=%s",
            payload.user_id,
            raw_candidates_total,
            raw_candidates_total,
            len(raw_candidates),
            ranking_debug["after_meal_like_filter"],
            ranking_debug["after_latest_service_date"],
            ranking_debug["latest_service_fallback_used"],
            ranking_debug["preference_ranking_pool"],
            ranking_debug["preference_signal_items"],
            ranking_debug["favorites_in_pool"],
            ranking_debug["ranked_candidates"],
            ranking_debug["top_ranked"],
        )
        interpreted_intent = self._detect_follow_up_intent(payload.message)
        is_follow_up_refinement = self._is_follow_up_refinement(
            interpreted_intent=interpreted_intent,
            context=payload.conversation_context,
        )

        if not menu_candidates:
            logger.info(
                "chat_reco_debug user_id=%s stage=result no_match=true reason=no_safe_meal_like_candidates",
                payload.user_id,
            )
            return self._attach_chat_context(
                response=self._build_chat_no_match_response(payload.lang),
                menu_candidates=[],
                recommended_item_id=None,
                interpreted_intent=interpreted_intent,
            )

        if is_follow_up_refinement:
            logger.info(
                "chat_reco_debug user_id=%s stage=follow_up intent=%s previous_recommended=%s",
                payload.user_id,
                interpreted_intent,
                payload.conversation_context.last_recommended_item_id
                if payload.conversation_context
                else None,
            )
            follow_up_response, recommended_item_id = self._build_follow_up_refinement_response(
                lang=payload.lang,
                intent=interpreted_intent,
                menu_candidates=menu_candidates,
                previous_recommended_item_id=payload.conversation_context.last_recommended_item_id
                if payload.conversation_context
                else None,
                previous_ranked_candidate_ids=payload.conversation_context.last_ranked_candidate_ids
                if payload.conversation_context
                else None,
            )
            return self._attach_chat_context(
                response=follow_up_response,
                menu_candidates=menu_candidates,
                recommended_item_id=recommended_item_id,
                interpreted_intent=interpreted_intent,
            )

        # Deterministic graceful fallback when query does not have a strong meal-like match.
        if top_score < 18:
            return self._attach_chat_context(
                response=self._build_chat_soft_match_response(payload.lang, menu_candidates[0]),
                menu_candidates=menu_candidates,
                recommended_item_id=menu_candidates[0].id,
                interpreted_intent=interpreted_intent,
            )

        try:
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
            canonical_item = next(
                (item for item in menu_candidates if item.id == filtered_recommended_ids[0]),
                menu_candidates[0],
            )
            normalized_reply = self._ensure_reply_mentions_item(
                lang=payload.lang,
                reply=validated.reply,
                item=canonical_item,
            )

            citations = [f"{chunk.source_type.value}:{chunk.source_id}" for chunk in chunks]

            return self._attach_chat_context(
                response=validated.model_copy(
                    update={
                        "reply": normalized_reply,
                        "recommended_dish_ids": filtered_recommended_ids,
                        "avoid_dish_ids": [
                            item_id for item_id in validated.avoid_dish_ids if item_id in allowed_ids
                        ],
                        "citations": citations[:5] if not validated.citations else validated.citations[:5],
                    }
                ),
                menu_candidates=menu_candidates,
                recommended_item_id=filtered_recommended_ids[0] if filtered_recommended_ids else None,
                interpreted_intent=interpreted_intent,
            )
        except (OpenRouterError, ValidationError) as error:
            logger.warning(
                "Chat recommendation fallback triggered for user_id=%s: %s",
                payload.user_id,
                error,
            )
            return self._attach_chat_context(
                response=self._build_chat_model_fallback_response(
                    lang=payload.lang,
                    item=menu_candidates[0],
                    preferences=preferences,
                    is_favorite=menu_candidates[0].id in favorite_ids,
                ),
                menu_candidates=menu_candidates,
                recommended_item_id=menu_candidates[0].id,
                interpreted_intent=interpreted_intent,
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
    ) -> tuple[list[MenuItem], int, dict[str, object]]:
        meal_like_items = [item for item in items if InsightService._is_meal_like_item(item)]
        latest_service_items = InsightService._restrict_to_latest_service_date(meal_like_items)
        latest_service_fallback_used = False
        same_day_items = latest_service_items
        if meal_like_items and not latest_service_items:
            # Keep today's visible, safe, meal-like pool if date metadata is inconsistent.
            same_day_items = meal_like_items
            latest_service_fallback_used = True

        debug: dict[str, object] = {
            "after_meal_like_filter": len(meal_like_items),
            "after_latest_service_date": len(latest_service_items),
            "latest_service_fallback_used": latest_service_fallback_used,
            "preference_ranking_pool": len(same_day_items),
            "preference_signal_items": 0,
            "favorites_in_pool": sum(1 for item in same_day_items if item.id in favorite_ids),
            "ranked_candidates": 0,
            "top_ranked": [],
        }
        if not same_day_items:
            return [], 0, debug

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

        ranked: list[tuple[int, MenuItem, int, bool]] = []
        for item in same_day_items:
            text = (
                f"{item.name_en} {item.name_zh} {item.station_name or ''} "
                f"{item.external_location_name or ''} {item.meal_name or ''}"
            ).lower()
            score = 0
            tag_values = [tag.value for tag in item.tags]
            tag_value_set = set(tag_values)
            allergen_values = [tag.value for tag in item.allergens]
            preference_match_count = sum(1 for tag in item.tags if tag.value in preferred_tag_values)
            is_favorite = item.id in favorite_ids

            if is_favorite:
                score += 120
            if preferred_meal_slot and item.meal_slot == preferred_meal_slot:
                score += 25
            if preferred_hall and item.hall_id == preferred_hall:
                score += 12
            preference_score = 0
            for pref in preferred_tag_values:
                if pref in tag_value_set:
                    preference_score += 22
                    continue
                if pref == "high-protein" and item.macros.protein >= 18:
                    preference_score += 12
                    continue
                if pref == "low-calorie" and item.calories <= 380:
                    preference_score += 9
                    continue
                if pref in {"halal", "kosher"}:
                    preference_score -= 8
                elif pref in {"vegan", "vegetarian"}:
                    preference_score -= 5
            score += preference_score
            score += sum(4 for token in tokens if token in text)

            if 180 <= item.calories <= 950:
                score += 5

            if wants_light and ("low-calorie" in tag_values or item.calories <= 380):
                score += 8
            if wants_seafood and ("fish" in allergen_values or "shellfish" in allergen_values):
                score += 10
            if wants_breakfast and item.meal_slot.value == "breakfast":
                score += 10
            if wants_high_protein and ("high-protein" in tag_values or item.macros.protein >= 18):
                score += 10

            ranked.append((score, item, preference_match_count, is_favorite))

        ranked.sort(key=lambda pair: pair[0], reverse=True)
        if not ranked:
            return [], 0, debug

        debug["ranked_candidates"] = len(ranked)
        debug["preference_signal_items"] = sum(
            1 for _, _, preference_match_count, _ in ranked if preference_match_count > 0
        )
        debug["top_ranked"] = [
            {
                "name": item.name_en,
                "score": int(score),
                "favorite": is_favorite,
                "preference_matches": preference_match_count,
            }
            for score, item, preference_match_count, is_favorite in ranked[:3]
        ]

        top_score = int(ranked[0][0])
        return [item for _, item, _, _ in ranked[:limit]], top_score, debug

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
    def _attach_chat_context(
        response: ChatRecommendationResponse,
        menu_candidates: list[MenuItem],
        recommended_item_id: str | None,
        interpreted_intent: str,
    ) -> ChatRecommendationResponse:
        return response.model_copy(
            update={
                "final_recommended_item_id": recommended_item_id,
                "conversation_context": ChatConversationContext(
                    last_recommended_item_id=recommended_item_id,
                    last_ranked_candidate_ids=[item.id for item in menu_candidates[:8]],
                    last_interpreted_intent=interpreted_intent,
                )
            }
        )

    @staticmethod
    def _detect_follow_up_intent(message: str) -> str:
        text = message.lower()
        intent_keywords: list[tuple[str, list[str]]] = [
            ("lighter", ["lighter", "light", "less heavy", "低卡", "清淡", "轻食", "更轻"]),
            ("more_filling", ["more filling", "filling", "heavier", "substantial", "更饱", "管饱", "更顶饱"]),
            ("less_greasy", ["less greasy", "not greasy", "less oil", "少油", "不油", "清爽"]),
            ("warmer", ["warmer", "warm", "hot", "soup", "更热", "暖一点", "热汤"]),
            ("vegetarian", ["vegetarian", "vegan", "plant-based", "素食", "吃素", "全素"]),
            ("higher_protein", ["higher protein", "more protein", "protein", "高蛋白", "增肌"]),
            ("seafood", ["seafood", "fish", "salmon", "shrimp", "海鲜", "鱼", "三文鱼", "虾"]),
        ]
        for intent, keywords in intent_keywords:
            if any(keyword in text for keyword in keywords):
                return intent
        return "general"

    @staticmethod
    def _is_follow_up_refinement(
        interpreted_intent: str,
        context: ChatConversationContext | None,
    ) -> bool:
        if interpreted_intent == "general" or context is None:
            return False
        return bool(context.last_recommended_item_id or context.last_ranked_candidate_ids)

    @staticmethod
    def _item_name_for_lang(item: MenuItem, lang: str) -> str:
        return item.name_zh if lang == "zh" and item.name_zh else item.name_en

    @staticmethod
    def _ensure_reply_mentions_item(lang: str, reply: str, item: MenuItem) -> str:
        item_name = InsightService._item_name_for_lang(item, lang)
        clean_reply = (reply or "").strip()
        if not clean_reply:
            return (
                f"今天更推荐「{item_name}」。"
                if lang == "zh"
                else f"I'd recommend {item_name}."
            )
        if item_name.lower() in clean_reply.lower():
            return clean_reply
        prefix = (
            f"今天更推荐「{item_name}」。"
            if lang == "zh"
            else f"I'd recommend {item_name}. "
        )
        return f"{prefix}{clean_reply}"

    @staticmethod
    def _score_for_follow_up_intent(intent: str, item: MenuItem) -> float:
        name_text = f"{item.name_en} {item.name_zh} {item.station_name or ''}".lower()
        tag_values = {tag.value for tag in item.tags}
        allergen_values = {tag.value for tag in item.allergens}
        warm_tokens = ["soup", "stew", "ramen", "curry", "hot", "汤", "热", "暖"]
        is_warm = any(token in name_text for token in warm_tokens)
        is_vegetarian = "vegetarian" in tag_values or "vegan" in tag_values
        is_seafood = (
            "fish" in allergen_values
            or "shellfish" in allergen_values
            or any(token in name_text for token in ["fish", "salmon", "shrimp", "seafood", "鱼", "虾", "海鲜"])
        )

        if intent == "lighter":
            return -(
                float(item.calories)
                + float(item.macros.fat) * 30.0
                + float(item.macros.carbs) * 2.0
            )
        if intent == "more_filling":
            return (
                float(item.calories)
                + float(item.macros.protein) * 6.0
                + float(item.macros.carbs) * 3.0
                + float(item.macros.fat) * 2.0
            )
        if intent == "less_greasy":
            return -(float(item.macros.fat) * 35.0 + float(item.calories) * 0.2)
        if intent == "warmer":
            return 100.0 if is_warm else 0.0
        if intent == "vegetarian":
            return 100.0 if is_vegetarian else -50.0
        if intent == "higher_protein":
            return (
                float(item.macros.protein) * 10.0
                + (40.0 if "high-protein" in tag_values else 0.0)
                - float(item.calories) * 0.1
            )
        if intent == "seafood":
            return 100.0 if is_seafood else -50.0
        return 0.0

    @staticmethod
    def _build_follow_up_refinement_response(
        lang: str,
        intent: str,
        menu_candidates: list[MenuItem],
        previous_recommended_item_id: str | None,
        previous_ranked_candidate_ids: list[str] | None = None,
    ) -> tuple[ChatRecommendationResponse, str]:
        comparison_pool = menu_candidates
        if previous_ranked_candidate_ids:
            by_id = {item.id: item for item in menu_candidates}
            contextual_pool = [
                by_id[item_id]
                for item_id in previous_ranked_candidate_ids
                if item_id in by_id
            ]
            if contextual_pool:
                comparison_pool = contextual_pool

        previous_item = next(
            (item for item in comparison_pool if item.id == previous_recommended_item_id),
            comparison_pool[0],
        )
        best_item = max(
            comparison_pool,
            key=lambda item: InsightService._score_for_follow_up_intent(intent, item),
        )

        previous_score = InsightService._score_for_follow_up_intent(intent, previous_item)
        best_score = InsightService._score_for_follow_up_intent(intent, best_item)
        is_meaningfully_better = best_item.id != previous_item.id and best_score > previous_score + 0.5
        chosen = best_item if is_meaningfully_better else previous_item

        chosen_name = InsightService._item_name_for_lang(chosen, lang)
        previous_name = InsightService._item_name_for_lang(previous_item, lang)
        intent_labels = {
            "lighter": ("更轻一点", "lighter"),
            "more_filling": ("更有饱腹感", "more filling"),
            "less_greasy": ("更少油", "less greasy"),
            "warmer": ("更暖一点", "warmer"),
            "vegetarian": ("改成素食", "vegetarian instead"),
            "higher_protein": ("更高蛋白", "higher protein"),
            "seafood": ("改成海鲜", "seafood instead"),
        }
        zh_label, en_label = intent_labels.get(intent, ("再细化一下", "refine this"))

        if is_meaningfully_better:
            if lang == "zh":
                reply = (
                    f"如果你想{zh_label}，我会把推荐从「{previous_name}」换成「{chosen_name}」。"
                    f"它在这个方向上更合适。"
                )
            else:
                reply = (
                    f"If you want {en_label}, I'd switch from {previous_name} to {chosen_name}. "
                    "It is a better fit for that direction."
                )
        else:
            if lang == "zh":
                reply = (
                    f"如果你想{zh_label}，「{previous_name}」仍然是今天可见且安全候选里更合适的一项。"
                    "当前没有明显更好的替代。"
                )
            else:
                reply = (
                    f"If you want {en_label}, {previous_name} is still the best fit among today's visible safe options. "
                    "There isn't a clearly better alternative right now."
                )

        return (
            ChatRecommendationResponse(
                reply=reply,
                recommended_dish_ids=[chosen.id],
                avoid_dish_ids=[],
                citations=[],
            ),
            chosen.id,
        )

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

    @staticmethod
    def _build_chat_model_fallback_response(
        lang: str,
        item: MenuItem,
        preferences: UserPreferences,
        is_favorite: bool,
    ) -> ChatRecommendationResponse:
        dish_name = item.name_zh if lang == "zh" and item.name_zh else item.name_en
        pref_values = [tag.value for tag in preferences.pref_tags][:2]
        has_allergen_settings = bool(preferences.allergen_tags)

        if lang == "zh":
            reason_parts = ["这是基于你当前需求和今日可见菜单筛出的优先项。"]
            if is_favorite:
                reason_parts.append("它也在你的收藏里。")
            elif pref_values:
                reason_parts.append(f"它和你的偏好方向更贴近（{', '.join(pref_values)}）。")
            if has_allergen_settings:
                reason_parts.append("并已优先避开你的过敏设置。")
            reply = f"今天可以优先考虑「{dish_name}」。" + "".join(reason_parts)
        else:
            reason_parts = ["It best matches your current request and today's visible menu."]
            if is_favorite:
                reason_parts.append("It's also in your favorites.")
            elif pref_values:
                reason_parts.append(f"It aligns with your preference focus ({', '.join(pref_values)}).")
            if has_allergen_settings:
                reason_parts.append("It also respects your allergen settings.")
            reply = f"A strong option for today is {dish_name}. " + " ".join(reason_parts)

        return ChatRecommendationResponse(
            reply=reply,
            recommended_dish_ids=[item.id],
            avoid_dish_ids=[],
            citations=[],
        )
