from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.db.repositories.menu_repository import MenuRepository
from app.db.repositories.rag_repository import RagRepository
from app.models.enums import SourceType
from app.models.menu import MenuItem
from app.services.embedding_service import EmbeddingService
from app.services.openrouter_service import OpenRouterService


class ChatService:
    def __init__(
        self,
        settings: Settings,
        menu_repo: MenuRepository,
        rag_repo: RagRepository,
        embedding_service: EmbeddingService,
        openrouter_service: OpenRouterService,
    ) -> None:
        self._settings = settings
        self._menu_repo = menu_repo
        self._rag_repo = rag_repo
        self._embedding_service = embedding_service
        self._openrouter = openrouter_service

    async def stream_chat(self, message: str) -> AsyncIterator[str]:
        user_message = message.strip()
        if not user_message:
            raise ValueError("message must not be empty")

        service_date = self._service_date_today()
        await self._upsert_daily_menu_embeddings(service_date)

        query_embedding = await self._embedding_service.embed_text(user_message)
        matches = await self._rag_repo.search_daily_menu_items_by_rpc(
            embedding=query_embedding,
            service_date=service_date,
            top_k=3,
        )

        system_prompt = self._build_system_prompt(
            service_date=service_date,
            matched_items=matches,
        )

        async for token in self._openrouter.stream_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_message,
            temperature=0.2,
            max_tokens=800,
        ):
            yield token

    async def _upsert_daily_menu_embeddings(self, service_date: date) -> None:
        menu_items = await self._menu_repo.list_menu_items(service_date=service_date)
        if not menu_items:
            return

        contents = [self._serialize_menu_item(item) for item in menu_items]
        embeddings = await self._embedding_service.embed_texts(contents)
        metadatas = [self._build_chunk_metadata(item) for item in menu_items]

        await self._rag_repo.upsert_chunks(
            source_type=SourceType.menu,
            source_ids=[item.id for item in menu_items],
            contents=contents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    @staticmethod
    def _serialize_menu_item(item: MenuItem) -> str:
        description = item.description.strip() if item.description else "N/A"
        tags = ", ".join(tag.value for tag in item.tags) if item.tags else "none"
        allergens = ", ".join(tag.value for tag in item.allergens) if item.allergens else "none"
        station_name = item.station_name or "N/A"
        meal_name = item.meal_name or item.meal_slot.value
        service_date = item.service_date.isoformat() if item.service_date else "N/A"

        lines = [
            f"id: {item.id}",
            f"name_en: {item.name_en}",
            f"name_zh: {item.name_zh}",
            f"description: {description}",
            f"hall_id: {item.hall_id.value}",
            f"meal_slot: {item.meal_slot.value}",
            f"meal_name: {meal_name}",
            f"station_name: {station_name}",
            f"service_date: {service_date}",
            f"calories: {item.calories}",
            f"protein_g: {item.macros.protein}",
            f"carbs_g: {item.macros.carbs}",
            f"fat_g: {item.macros.fat}",
            f"dietary_tags: {tags}",
            f"allergens: {allergens}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_chunk_metadata(item: MenuItem) -> dict[str, Any]:
        return {
            "name_en": item.name_en,
            "name_zh": item.name_zh,
            "hall_id": item.hall_id.value,
            "meal_slot": item.meal_slot.value,
            "service_date": item.service_date.isoformat() if item.service_date else None,
            "station_name": item.station_name,
            "calories": item.calories,
            "protein": item.macros.protein,
            "carbs": item.macros.carbs,
            "fat": item.macros.fat,
        }

    def _service_date_today(self) -> date:
        timezone = ZoneInfo(self._settings.menu_sync_timezone)
        return datetime.now(timezone).date()

    def _build_system_prompt(
        self,
        service_date: date,
        matched_items: list[dict[str, Any]],
    ) -> str:
        context = json.dumps(
            [self._normalize_match_payload(item) for item in matched_items],
            ensure_ascii=False,
            indent=2,
        )

        return (
            "You are a Brown dining nutrition assistant.\n"
            "You must answer using only the retrieved dishes in RETRIEVED_DISHES_JSON.\n"
            "If the retrieved list is empty, clearly say no matching dish is available today.\n"
            "Do not fabricate dish names, nutrition values, or availability.\n"
            "Prefer concise and practical suggestions.\n"
            "Reply in the same language as the user.\n"
            f"TODAY_SERVICE_DATE: {service_date.isoformat()}\n"
            "RETRIEVED_DISHES_JSON:\n"
            f"{context}"
        )

    @staticmethod
    def _normalize_match_payload(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "menu_item_id": str(item.get("menu_item_id", "")),
            "name_en": item.get("name_en"),
            "name_zh": item.get("name_zh"),
            "description": item.get("description"),
            "hall_id": item.get("hall_id"),
            "meal_slot": item.get("meal_slot"),
            "meal_name": item.get("meal_name"),
            "station_name": item.get("station_name"),
            "nutrition": {
                "calories": ChatService._coerce_number(item.get("calories")),
                "protein": ChatService._coerce_number(item.get("protein")),
                "carbs": ChatService._coerce_number(item.get("carbs")),
                "fat": ChatService._coerce_number(item.get("fat")),
                "nutrition_available": bool(item.get("nutrition_available", False)),
            },
            "tags": item.get("tags") or [],
            "allergens": item.get("allergens") or [],
            "similarity": ChatService._coerce_number(item.get("similarity")),
        }

    @staticmethod
    def _coerce_number(value: Any) -> float | int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return round(value, 4)
        if isinstance(value, Decimal):
            return round(float(value), 4)
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return None
