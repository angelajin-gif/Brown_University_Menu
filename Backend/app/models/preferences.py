from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import AllergenTag, DietaryTag, HallId


TIME_PATTERN = r"^(?:[01]\d|2[0-3]):[0-5]\d$"


class NotificationTimes(BaseModel):
    breakfast: str = Field(default="07:30", pattern=TIME_PATTERN)
    lunch: str = Field(default="11:45", pattern=TIME_PATTERN)
    dinner: str = Field(default="17:30", pattern=TIME_PATTERN)


class NotificationSettings(BaseModel):
    allow_notifications: bool = False
    times: NotificationTimes = Field(default_factory=NotificationTimes)


class UserPreferences(BaseModel):
    user_id: str
    favorite_hall: HallId = HallId.hall1
    ai_auto_push: bool = True
    pref_tags: list[DietaryTag] = Field(default_factory=list)
    allergen_tags: list[AllergenTag] = Field(default_factory=list)


class UserPreferencesUpdateRequest(BaseModel):
    favorite_hall: HallId | None = None
    ai_auto_push: bool | None = None
    pref_tags: list[DietaryTag] | None = None
    allergen_tags: list[AllergenTag] | None = None


class NotificationSettingsUpdateRequest(BaseModel):
    allow_notifications: bool | None = None
    times: NotificationTimes | None = None


class FavoritesResponse(BaseModel):
    user_id: str
    menu_item_ids: list[str]


class FavoritesUpdateRequest(BaseModel):
    menu_item_ids: list[str] = Field(default_factory=list)
