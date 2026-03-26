from __future__ import annotations

from datetime import date

from app.db.repositories.menu_repository import MenuRepository
from app.db.repositories.user_repository import UserRepository
from app.models.enums import HallId, MealSlot
from app.models.menu import MenuItem


class MenuService:
    def __init__(self, menu_repo: MenuRepository, user_repo: UserRepository) -> None:
        self._menu_repo = menu_repo
        self._user_repo = user_repo

    async def list_menu_items(
        self,
        user_id: str | None,
        meal_slot: MealSlot | None,
        hall_id: HallId | None,
        query: str | None,
        service_date: date | None,
        respect_user_allergens: bool = True,
    ) -> list[MenuItem]:
        exclude_allergens = None
        if user_id and respect_user_allergens:
            preferences = await self._user_repo.get_preferences(user_id)
            exclude_allergens = preferences.allergen_tags

        return await self._menu_repo.list_menu_items(
            meal_slot=meal_slot,
            hall_id=hall_id,
            query=query,
            service_date=service_date,
            exclude_allergens=exclude_allergens,
        )

    async def get_menu_item(self, item_id: str) -> MenuItem | None:
        return await self._menu_repo.get_menu_item(item_id)
