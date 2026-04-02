from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BrownBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        strict=True,
    )


class BrownHours(BrownBaseModel):
    start_at: datetime = Field(alias="start")
    end_at: datetime = Field(alias="end")

    @field_validator("start_at", "end_at", mode="before")
    @classmethod
    def parse_iso_datetime(cls, value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.endswith("Z"):
                normalized = f"{normalized[:-1]}+00:00"
            return datetime.fromisoformat(normalized)
        raise TypeError("Expected ISO datetime string or datetime value.")


class BrownMenuItem(BrownBaseModel):
    item_id: int = Field(alias="itemId")
    item_name: str = Field(alias="item")
    icons: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    description: str = ""
    item_type: str = Field(alias="itemType")


class BrownStation(BrownBaseModel):
    station_id: str | int = Field(alias="stationId")
    name: str
    items: list[BrownMenuItem] = Field(default_factory=list)


class BrownMenu(BrownBaseModel):
    date: str
    hours: BrownHours
    stations: list[BrownStation] = Field(default_factory=list)


class BrownMeal(BrownBaseModel):
    meal_name: str = Field(alias="meal")
    display_name: str = Field(alias="name")
    menu: BrownMenu


class BrownLocationMenu(BrownBaseModel):
    location_address: str = Field(alias="locationAddress")
    location_id: str = Field(alias="locationId")
    name: str
    meals: dict[str, list[BrownMeal]] = Field(default_factory=dict)
