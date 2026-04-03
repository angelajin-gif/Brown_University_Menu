from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import HallId, MealSlot


class NutritionSummary(BaseModel):
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)


class CustomStationSelectionInput(BaseModel):
    menu_item_id: str = Field(min_length=1, max_length=200)
    servings: float = Field(default=1.0, gt=0, le=20)


class CustomStationNutritionRequest(BaseModel):
    selections: list[CustomStationSelectionInput] = Field(min_length=1, max_length=80)
    station_name: str | None = Field(default=None, max_length=120)
    service_date: date | None = None


class CustomStationSelectionDetail(BaseModel):
    menu_item_id: str
    name_en: str
    name_zh: str
    hall_id: HallId
    meal_slot: MealSlot
    station_name: str | None = None
    service_date: date | None = None
    item_type: str | None = None
    nutrition_available: bool
    servings: float = Field(gt=0)
    per_serving: NutritionSummary
    subtotal: NutritionSummary


class CustomStationNutritionResponse(BaseModel):
    station_name: str | None = None
    service_date: date | None = None
    selections: list[CustomStationSelectionDetail]
    totals: NutritionSummary
    missing_item_ids: list[str] = Field(default_factory=list)
    unavailable_nutrition_item_ids: list[str] = Field(default_factory=list)
    computed_at: datetime


class CustomStationComponent(BaseModel):
    id: str
    name_en: str
    name_zh: str
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)
    hall_id: HallId
    meal_slot: MealSlot
    station_name: str | None = None
    service_date: date | None = None
    item_type: str | None = None
    nutrition_available: bool = False
