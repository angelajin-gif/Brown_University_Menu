from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
from pydantic import TypeAdapter
from supabase import Client, create_client

from app.core.config import Settings
from app.models.brown_menu import BrownLocationMenu


ICON_TO_TAG = {
    "VGTN": "vegetarian",
    "VEGETARIAN": "vegetarian",
    "VGN": "vegan",
    "VEGAN": "vegan",
    "KSHR": "kosher",
    "KOSHER": "kosher",
    "HL": "halal",
    "HALAL": "halal",
    "SO": "shared-oil",
    "FRIED IN SHARED OIL": "shared-oil",
}

ALLERGEN_TO_TAG = {
    "WHEAT/GLUTEN": "gluten-free",
    "GLUTEN": "gluten-free",
    "DAIRY": "dairy",
    "ALCOHOL": "alcohol",
    "SOY": "soy",
    "EGG": "egg",
    "COCONUT": "coconut",
    "TREE NUTS": "tree-nuts",
    "TREE-NUTS": "tree-nuts",
    "SESAME": "sesame",
    "FISH": "fish",
    "SHELLFISH": "shellfish",
}

HALL1_LOCATION_IDS = {"AC", "SHRP", "VW"}
FIXED_DISH_ITEM_TYPE = "recipe"
CUSTOM_COMPONENT_ITEM_TYPE = "ingredient"
NUTRITION_ELIGIBLE_ITEM_TYPES = {FIXED_DISH_ITEM_TYPE, CUSTOM_COMPONENT_ITEM_TYPE}


class BrownMenuSyncService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(timeout=30)
        self._supabase = self._create_supabase_client(settings)

    async def close(self) -> None:
        await self._http.aclose()

    async def sync_menu_items(self) -> dict[str, str | int]:
        payload = await self._fetch_raw_payload()
        normalized_payload = self._normalize_payload_hours(payload)
        normalized_payload, normalized_null_counts = self._normalize_menu_item_nullable_fields(
            normalized_payload
        )
        normalized_null_total = sum(normalized_null_counts.values())
        print(
            "[brown-menu-sync] normalized null menu item fields "
            f"total={normalized_null_total} "
            f"icons={normalized_null_counts['icons']} "
            f"allergens={normalized_null_counts['allergens']} "
            f"description={normalized_null_counts['description']}"
        )
        locations = TypeAdapter(list[BrownLocationMenu]).validate_python(normalized_payload)

        service_date = self._service_date_today()
        records = self._transform_to_menu_upserts(locations, service_date)
        nutrition_candidates = sum(
            1 for record in records if self._is_nutrition_eligible_record(record)
        )

        nutrition_enriched = 0
        if self._settings.menu_sync_enrich_nutrition:
            nutrition_enriched = await self._enrich_records_with_nutrition(records)

        await asyncio.to_thread(self._deactivate_existing_for_date, service_date)
        await self._upsert_records(records)

        return {
            "service_date": service_date.isoformat(),
            "locations": len(locations),
            "upserted": len(records),
            "nutrition_candidates": nutrition_candidates,
            "nutrition_enriched": nutrition_enriched,
        }

    async def _fetch_raw_payload(self) -> list[dict]:
        response = await self._http.get(self._settings.brown_menu_api_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Brown menu payload must be a JSON array")
        return payload

    def _normalize_menu_item_nullable_fields(
        self,
        payload: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        counts = {
            "icons": 0,
            "allergens": 0,
            "description": 0,
        }

        def normalize_node(node: Any) -> None:
            if isinstance(node, list):
                for child in node:
                    normalize_node(child)
                return

            if not isinstance(node, dict):
                return

            is_menu_item = "itemId" in node and "item" in node and "itemType" in node
            if is_menu_item:
                if node.get("icons") is None:
                    node["icons"] = []
                    counts["icons"] += 1
                if node.get("allergens") is None:
                    node["allergens"] = []
                    counts["allergens"] += 1
                if node.get("description") is None:
                    node["description"] = ""
                    counts["description"] += 1

            for value in node.values():
                normalize_node(value)

        normalize_node(payload)
        return payload, counts

    @staticmethod
    def _parse_datetime_like(value: object) -> object:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.endswith("Z"):
                normalized = f"{normalized[:-1]}+00:00"
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                return value
        return value

    def _normalize_payload_hours(self, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for location in payload:
            meals = location.get("meals")
            if not isinstance(meals, dict):
                continue

            for meal_entries in meals.values():
                if not isinstance(meal_entries, list):
                    continue

                for meal in meal_entries:
                    if not isinstance(meal, dict):
                        continue
                    menu = meal.get("menu")
                    if not isinstance(menu, dict):
                        continue
                    hours = menu.get("hours")
                    if not isinstance(hours, dict):
                        continue

                    if "start" in hours:
                        hours["start"] = self._parse_datetime_like(hours.get("start"))
                    if "end" in hours:
                        hours["end"] = self._parse_datetime_like(hours.get("end"))

        return payload

    @staticmethod
    def _create_supabase_client(settings: Settings) -> Client:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for sync")
        return create_client(settings.supabase_url, settings.supabase_service_role_key)

    def _service_date_today(self) -> date:
        timezone = ZoneInfo(self._settings.menu_sync_timezone)
        return datetime.now(timezone).date()

    def _transform_to_menu_upserts(
        self,
        locations: list[BrownLocationMenu],
        service_date: date,
    ) -> list[dict]:
        records: list[dict] = []

        for location in locations:
            for date_key, meals in location.meals.items():
                try:
                    parsed_date = date.fromisoformat(date_key)
                except ValueError:
                    continue

                if self._settings.menu_sync_only_today and parsed_date != service_date:
                    continue

                for meal in meals:
                    meal_slot = self._map_meal_slot(meal.meal_name)
                    meal_slug = self._slugify(meal.meal_name)
                    for station in meal.menu.stations:
                        station_id = str(station.station_id)
                        station_slug = self._slugify(station_id)
                        for item in station.items:
                            item_type = item.item_type.strip().lower()
                            nutrition_item_id = str(item.item_id)
                            item_key = (
                                f"brown-{location.location_id}-{parsed_date.isoformat()}-"
                                f"{meal_slug}-{station_slug}-{item.item_id}"
                            )

                            records.append(
                                {
                                    "id": item_key,
                                    "name_en": item.item_name,
                                    "name_zh": item.item_name,
                                    "description": item.description,
                                    "calories": 0,
                                    "protein": 0,
                                    "carbs": 0,
                                    "fat": 0,
                                    "tags": self._map_icons(item.icons),
                                    "allergens": self._map_allergens(item.allergens),
                                    "hall_id": self._map_hall(location.location_id),
                                    "meal_slot": meal_slot,
                                    "is_active": True,
                                    "source": "brown",
                                    "external_location_id": location.location_id,
                                    "external_location_name": location.name,
                                    "station_id": station_id,
                                    "station_name": station.name,
                                    "service_date": parsed_date.isoformat(),
                                    "meal_name": meal.meal_name,
                                    "menu_start": meal.menu.hours.start_at.isoformat(),
                                    "menu_end": meal.menu.hours.end_at.isoformat(),
                                    "item_type": item_type,
                                    "nutrition_item_id": nutrition_item_id,
                                    "nutrition_source_url": self._build_nutrition_source_url(
                                        nutrition_item_id,
                                        item_type,
                                    ),
                                    "nutrition_available": False,
                                    "nutrition_synced_at": None,
                                    "updated_at": datetime.utcnow().isoformat(),
                                }
                            )

        return records

    @staticmethod
    def _is_fixed_dish_record(record: dict[str, Any]) -> bool:
        return str(record.get("item_type", "")).strip().lower() == FIXED_DISH_ITEM_TYPE

    @staticmethod
    def _is_nutrition_eligible_record(record: dict[str, Any]) -> bool:
        item_type = str(record.get("item_type", "")).strip().lower()
        return item_type in NUTRITION_ELIGIBLE_ITEM_TYPES

    async def _enrich_records_with_nutrition(self, records: list[dict[str, Any]]) -> int:
        nutrition_keys = sorted(
            {
                (
                    str(record.get("nutrition_item_id", "")).strip(),
                    str(record.get("item_type", "")).strip().lower(),
                )
                for record in records
                if self._is_nutrition_eligible_record(record)
                and str(record.get("nutrition_item_id", "")).strip()
            }
        )
        if not nutrition_keys:
            return 0

        semaphore = asyncio.Semaphore(max(1, self._settings.menu_sync_nutrition_concurrency))
        nutrition_by_key: dict[tuple[str, str], dict[str, float | int]] = {}

        async def fetch_and_store(item_id: str, item_type: str) -> None:
            async with semaphore:
                nutrition = await self._fetch_item_nutrition(item_id, item_type)
                if nutrition is not None:
                    nutrition_by_key[(item_id, item_type)] = nutrition

        await asyncio.gather(
            *(fetch_and_store(item_id, item_type) for item_id, item_type in nutrition_keys)
        )

        nutrition_synced_at = datetime.utcnow().isoformat()
        enriched_count = 0
        for record in records:
            record["nutrition_synced_at"] = nutrition_synced_at

            if not self._is_nutrition_eligible_record(record):
                record["nutrition_available"] = False
                continue

            nutrition_item_id = str(record.get("nutrition_item_id", "")).strip()
            item_type = str(record.get("item_type", "")).strip().lower()
            nutrition = nutrition_by_key.get((nutrition_item_id, item_type))
            if nutrition is None:
                record["nutrition_available"] = False
                continue

            record["calories"] = nutrition["calories"]
            record["protein"] = nutrition["protein"]
            record["carbs"] = nutrition["carbs"]
            record["fat"] = nutrition["fat"]
            record["nutrition_available"] = True
            enriched_count += 1

        return enriched_count

    async def _fetch_item_nutrition(
        self,
        item_id: str,
        item_type: str,
    ) -> dict[str, float | int] | None:
        try:
            response = await self._http.get(
                self._settings.brown_nutrition_api_url,
                params={"id": item_id, "type": item_type},
            )
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None

        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("success") is False:
            return None

        base_values = payload.get("baseValues")
        if not isinstance(base_values, dict):
            return None

        calories = self._coerce_calories_value(base_values.get("calories"))
        protein = self._coerce_macro_value(base_values.get("protein"))
        carbs = self._coerce_macro_value(base_values.get("carbohydrates"))
        fat = self._coerce_macro_value(base_values.get("fat"))
        if calories is None or protein is None or carbs is None or fat is None:
            return None

        return {
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
        }

    @staticmethod
    def _coerce_calories_value(value: Any) -> int | None:
        amount = BrownMenuSyncService._extract_amount(value)
        if amount is None:
            return None
        return int(round(amount))

    @staticmethod
    def _coerce_macro_value(value: Any) -> float | None:
        amount = BrownMenuSyncService._extract_amount(value)
        if amount is None:
            return None
        return round(amount, 2)

    @staticmethod
    def _extract_amount(value: Any) -> float | None:
        raw_value = value
        if isinstance(value, dict):
            raw_value = value.get("amount")

        if isinstance(raw_value, (int, float)):
            amount = float(raw_value)
            return amount if amount >= 0 else None

        if isinstance(raw_value, str):
            match = re.search(r"-?\d+(?:\.\d+)?", raw_value.replace(",", ""))
            if match:
                amount = float(match.group(0))
                return amount if amount >= 0 else None

        return None

    def _build_nutrition_source_url(self, item_id: str, item_type: str) -> str:
        base_url = self._settings.brown_nutrition_public_base_url.rstrip("/")
        query = urlencode({"type": item_type})
        return f"{base_url}/{item_id}?{query}"

    @staticmethod
    def _map_meal_slot(meal_name: str) -> str:
        normalized = meal_name.lower()
        if "breakfast" in normalized:
            return "breakfast"
        if "dinner" in normalized or "supper" in normalized:
            return "dinner"
        return "lunch"

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "unknown"

    @staticmethod
    def _map_hall(location_id: str) -> str:
        return "hall1" if location_id in HALL1_LOCATION_IDS else "hall2"

    @staticmethod
    def _unique_preserving_order(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    def _map_icons(self, icons: list[str]) -> list[str]:
        mapped = [ICON_TO_TAG.get(icon.strip().upper()) for icon in icons]
        return self._unique_preserving_order([item for item in mapped if item])

    def _map_allergens(self, allergens: list[str]) -> list[str]:
        mapped = [ALLERGEN_TO_TAG.get(item.strip().upper()) for item in allergens]
        return self._unique_preserving_order([item for item in mapped if item])

    def _deactivate_existing_for_date(self, service_date: date) -> None:
        self._supabase.table("menu_items").update({"is_active": False}).eq("source", "brown").eq(
            "service_date", service_date.isoformat()
        ).execute()

    async def _upsert_records(self, records: list[dict]) -> None:
        if not records:
            return

        records = self._dedupe_records_by_id(records)
        batch_size = max(1, self._settings.menu_sync_batch_size)
        for index in range(0, len(records), batch_size):
            chunk = records[index : index + batch_size]
            await asyncio.to_thread(self._upsert_chunk, chunk)

    def _upsert_chunk(self, records: list[dict]) -> None:
        self._supabase.table("menu_items").upsert(records, on_conflict="id").execute()

    @staticmethod
    def _dedupe_records_by_id(records: list[dict]) -> list[dict]:
        before_count = len(records)
        deduped_by_id: dict[str, dict] = {}

        for record in records:
            record_id = str(record.get("id", ""))
            if record_id in deduped_by_id:
                deduped_by_id.pop(record_id)
            deduped_by_id[record_id] = record

        deduped_records = list(deduped_by_id.values())
        after_count = len(deduped_records)
        removed_count = before_count - after_count
        print(
            f"[brown-menu-sync] dedupe records before={before_count} "
            f"after={after_count} removed={removed_count}"
        )
        return deduped_records
