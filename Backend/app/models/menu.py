from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import AllergenTag, DietaryTag, HallId, MealSlot


class Macronutrients(BaseModel):
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)


class MenuItem(BaseModel):
    id: str
    name_en: str
    name_zh: str
    description: str | None = None
    calories: int = Field(ge=0)
    macros: Macronutrients
    tags: list[DietaryTag] = Field(default_factory=list)
    allergens: list[AllergenTag] = Field(default_factory=list)
    hall_id: HallId
    meal_slot: MealSlot
    service_date: date | None = None
    external_location_id: str | None = None
    external_location_name: str | None = None
    station_name: str | None = None
    meal_name: str | None = None
    menu_start: datetime | None = None
    menu_end: datetime | None = None


class MenuListResponse(BaseModel):
    items: list[MenuItem]
    total: int
