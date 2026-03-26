from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
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


class BrownMenuSyncService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(timeout=30)
        self._supabase = self._create_supabase_client(settings)

    async def close(self) -> None:
        await self._http.aclose()

    async def sync_menu_items(self) -> dict[str, str | int]:
        payload = await self._fetch_raw_payload()
        locations = TypeAdapter(list[BrownLocationMenu]).validate_python(payload)

        service_date = self._service_date_today()
        records = self._transform_to_menu_upserts(locations, service_date)

        await asyncio.to_thread(self._deactivate_existing_for_date, service_date)
        await self._upsert_records(records)

        return {
            "service_date": service_date.isoformat(),
            "locations": len(locations),
            "upserted": len(records),
        }

    async def _fetch_raw_payload(self) -> list[dict]:
        response = await self._http.get(self._settings.brown_menu_api_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Brown menu payload must be a JSON array")
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
                                    "item_type": item.item_type,
                                    "updated_at": datetime.utcnow().isoformat(),
                                }
                            )

        return records

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

        batch_size = max(1, self._settings.menu_sync_batch_size)
        for index in range(0, len(records), batch_size):
            chunk = records[index : index + batch_size]
            await asyncio.to_thread(self._upsert_chunk, chunk)

    def _upsert_chunk(self, records: list[dict]) -> None:
        self._supabase.table("menu_items").upsert(records, on_conflict="id").execute()
