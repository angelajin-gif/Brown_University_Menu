from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone

from app.db.repositories.menu_repository import MenuRepository
from app.models.custom_station import (
    CustomStationNutritionRequest,
    CustomStationNutritionResponse,
    CustomStationSelectionDetail,
    NutritionSummary,
)


class CustomStationService:
    def __init__(self, menu_repo: MenuRepository) -> None:
        self._menu_repo = menu_repo

    async def calculate_nutrition(
        self,
        payload: CustomStationNutritionRequest,
    ) -> CustomStationNutritionResponse:
        servings_by_item_id = self._aggregate_servings(payload)
        requested_item_ids = list(servings_by_item_id.keys())

        components = await self._menu_repo.list_custom_station_components_by_ids(requested_item_ids)
        component_by_id = {item.id: item for item in components}

        missing_item_ids = [item_id for item_id in requested_item_ids if item_id not in component_by_id]
        unavailable_nutrition_item_ids: list[str] = []
        selection_details: list[CustomStationSelectionDetail] = []

        total_calories = 0.0
        total_protein = 0.0
        total_carbs = 0.0
        total_fat = 0.0

        for item_id in requested_item_ids:
            component = component_by_id.get(item_id)
            if component is None:
                continue

            servings = servings_by_item_id[item_id]
            nutrition_available = self._is_nutrition_available(component.nutrition_available, component)

            per_serving = NutritionSummary(
                calories=round(component.calories, 2),
                protein=round(component.protein, 2),
                carbs=round(component.carbs, 2),
                fat=round(component.fat, 2),
            )

            if nutrition_available:
                subtotal = NutritionSummary(
                    calories=round(component.calories * servings, 2),
                    protein=round(component.protein * servings, 2),
                    carbs=round(component.carbs * servings, 2),
                    fat=round(component.fat * servings, 2),
                )
                total_calories += subtotal.calories
                total_protein += subtotal.protein
                total_carbs += subtotal.carbs
                total_fat += subtotal.fat
            else:
                unavailable_nutrition_item_ids.append(item_id)
                subtotal = NutritionSummary(
                    calories=0,
                    protein=0,
                    carbs=0,
                    fat=0,
                )

            selection_details.append(
                CustomStationSelectionDetail(
                    menu_item_id=component.id,
                    name_en=component.name_en,
                    name_zh=component.name_zh,
                    hall_id=component.hall_id,
                    meal_slot=component.meal_slot,
                    station_name=component.station_name,
                    service_date=component.service_date,
                    item_type=component.item_type,
                    nutrition_available=nutrition_available,
                    servings=round(servings, 3),
                    per_serving=per_serving,
                    subtotal=subtotal,
                )
            )

        resolved_station_name = self._resolve_station_name(payload, selection_details)
        resolved_service_date = self._resolve_service_date(payload, selection_details)

        return CustomStationNutritionResponse(
            station_name=resolved_station_name,
            service_date=resolved_service_date,
            selections=selection_details,
            totals=NutritionSummary(
                calories=round(total_calories, 2),
                protein=round(total_protein, 2),
                carbs=round(total_carbs, 2),
                fat=round(total_fat, 2),
            ),
            missing_item_ids=missing_item_ids,
            unavailable_nutrition_item_ids=unavailable_nutrition_item_ids,
            computed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _aggregate_servings(payload: CustomStationNutritionRequest) -> OrderedDict[str, float]:
        servings_by_item_id: OrderedDict[str, float] = OrderedDict()
        for selection in payload.selections:
            item_id = selection.menu_item_id.strip()
            if not item_id:
                continue
            servings_by_item_id[item_id] = round(
                servings_by_item_id.get(item_id, 0.0) + float(selection.servings),
                6,
            )

        if not servings_by_item_id:
            raise ValueError("No valid menu_item_id found in selections.")
        return servings_by_item_id

    @staticmethod
    def _is_nutrition_available(flag: bool, component) -> bool:
        if flag:
            return True
        return (
            component.calories > 0
            or component.protein > 0
            or component.carbs > 0
            or component.fat > 0
        )

    @staticmethod
    def _resolve_station_name(
        payload: CustomStationNutritionRequest,
        details: list[CustomStationSelectionDetail],
    ) -> str | None:
        if payload.station_name and payload.station_name.strip():
            return payload.station_name.strip()

        station_names = {
            detail.station_name.strip()
            for detail in details
            if detail.station_name and detail.station_name.strip()
        }
        if len(station_names) == 1:
            return next(iter(station_names))
        return None

    @staticmethod
    def _resolve_service_date(
        payload: CustomStationNutritionRequest,
        details: list[CustomStationSelectionDetail],
    ):
        if payload.service_date is not None:
            return payload.service_date

        dates = {detail.service_date for detail in details if detail.service_date is not None}
        if len(dates) == 1:
            return next(iter(dates))
        return None
