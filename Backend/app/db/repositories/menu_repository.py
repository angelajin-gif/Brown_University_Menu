from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from app.db.postgres import Database
from app.models.enums import AllergenTag, DietaryTag, HallId, MealSlot
from app.models.menu import Macronutrients, MenuItem


class MenuRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    @staticmethod
    def _row_to_menu_item(row: dict) -> MenuItem:
        return MenuItem(
            id=row["id"],
            name_en=row["name_en"],
            name_zh=row["name_zh"],
            description=row.get("description"),
            calories=row["calories"],
            macros=Macronutrients(
                protein=float(row["protein"]),
                carbs=float(row["carbs"]),
                fat=float(row["fat"]),
            ),
            tags=[DietaryTag(tag) for tag in row.get("tags", [])],
            allergens=[AllergenTag(tag) for tag in row.get("allergens", [])],
            hall_id=HallId(row["hall_id"]),
            meal_slot=MealSlot(row["meal_slot"]),
            service_date=row.get("service_date"),
            external_location_id=row.get("external_location_id"),
            external_location_name=row.get("external_location_name"),
            station_name=row.get("station_name"),
            meal_name=row.get("meal_name"),
            menu_start=row.get("menu_start"),
            menu_end=row.get("menu_end"),
        )

    async def list_menu_items(
        self,
        meal_slot: MealSlot | None = None,
        hall_id: HallId | None = None,
        query: str | None = None,
        service_date: date | None = None,
        exclude_allergens: Sequence[AllergenTag] | None = None,
    ) -> list[MenuItem]:
        sql = """
            SELECT
                id,
                name_en,
                name_zh,
                description,
                calories,
                protein,
                carbs,
                fat,
                tags,
                allergens,
                hall_id,
                meal_slot,
                service_date,
                external_location_id,
                external_location_name,
                station_name,
                meal_name,
                menu_start,
                menu_end
            FROM menu_items
            WHERE is_active = TRUE
              AND ($1::text IS NULL OR meal_slot = $1)
              AND ($2::text IS NULL OR hall_id = $2)
              AND (
                    $3::text IS NULL
                    OR name_en ILIKE '%' || $3 || '%'
                    OR name_zh ILIKE '%' || $3 || '%'
              )
              AND (
                    $4::text[] IS NULL
                    OR array_length($4::text[], 1) IS NULL
                    OR NOT (allergens && $4::text[])
              )
              AND ($5::date IS NULL OR service_date = $5)
            ORDER BY
                CASE meal_slot
                    WHEN 'breakfast' THEN 1
                    WHEN 'lunch' THEN 2
                    WHEN 'dinner' THEN 3
                    ELSE 4
                END,
                id;
        """

        rows = await self._db.fetch(
            sql,
            meal_slot.value if meal_slot else None,
            hall_id.value if hall_id else None,
            query.strip() if query else None,
            [item.value for item in exclude_allergens] if exclude_allergens else None,
            service_date,
        )
        return [self._row_to_menu_item(dict(row)) for row in rows]

    async def get_menu_item(self, item_id: str) -> MenuItem | None:
        sql = """
            SELECT
                id,
                name_en,
                name_zh,
                description,
                calories,
                protein,
                carbs,
                fat,
                tags,
                allergens,
                hall_id,
                meal_slot,
                service_date,
                external_location_id,
                external_location_name,
                station_name,
                meal_name,
                menu_start,
                menu_end
            FROM menu_items
            WHERE id = $1 AND is_active = TRUE
            LIMIT 1;
        """
        row = await self._db.fetchrow(sql, item_id)
        if not row:
            return None
        return self._row_to_menu_item(dict(row))

    async def list_menu_items_by_ids(self, item_ids: Sequence[str]) -> list[MenuItem]:
        if not item_ids:
            return []

        sql = """
            SELECT
                id,
                name_en,
                name_zh,
                description,
                calories,
                protein,
                carbs,
                fat,
                tags,
                allergens,
                hall_id,
                meal_slot,
                service_date,
                external_location_id,
                external_location_name,
                station_name,
                meal_name,
                menu_start,
                menu_end
            FROM menu_items
            WHERE is_active = TRUE AND id = ANY($1::text[])
            ORDER BY array_position($1::text[], id);
        """
        rows = await self._db.fetch(sql, list(item_ids))
        return [self._row_to_menu_item(dict(row)) for row in rows]

    async def list_recommended_menu_items(
        self,
        preferred_tags: Sequence[DietaryTag],
        allergen_tags: Sequence[AllergenTag],
        favorite_hall: HallId | None,
        meal_slot: MealSlot | None,
        hall_id: HallId | None,
        service_date: date | None,
        limit: int = 5,
    ) -> list[MenuItem]:
        sql = """
            SELECT
                id,
                name_en,
                name_zh,
                description,
                calories,
                protein,
                carbs,
                fat,
                tags,
                allergens,
                hall_id,
                meal_slot,
                service_date,
                external_location_id,
                external_location_name,
                station_name,
                meal_name,
                menu_start,
                menu_end,
                COALESCE((
                    SELECT COUNT(*)
                    FROM unnest(tags) AS tag
                    WHERE tag = ANY($1::text[])
                ), 0) AS pref_score,
                CASE
                    WHEN $2::text IS NULL THEN 0
                    WHEN hall_id = $2::text THEN 1
                    ELSE 0
                END AS hall_score
            FROM menu_items
            WHERE is_active = TRUE
              AND ($3::text IS NULL OR meal_slot = $3)
              AND ($4::text IS NULL OR hall_id = $4)
              AND (
                    $5::text[] IS NULL
                    OR array_length($5::text[], 1) IS NULL
                    OR NOT (allergens && $5::text[])
              )
              AND ($6::date IS NULL OR service_date = $6)
            ORDER BY pref_score DESC, hall_score DESC, calories ASC
            LIMIT $7;
        """

        rows = await self._db.fetch(
            sql,
            [tag.value for tag in preferred_tags] if preferred_tags else [],
            favorite_hall.value if favorite_hall else None,
            meal_slot.value if meal_slot else None,
            hall_id.value if hall_id else None,
            [item.value for item in allergen_tags] if allergen_tags else None,
            service_date,
            limit,
        )
        return [self._row_to_menu_item(dict(row)) for row in rows]
