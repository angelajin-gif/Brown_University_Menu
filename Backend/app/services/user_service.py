from __future__ import annotations

from app.db.repositories.menu_repository import MenuRepository
from app.db.repositories.user_repository import UserRepository
from app.models.preferences import (
    FavoritesResponse,
    NotificationSettings,
    NotificationSettingsUpdateRequest,
    UserPreferences,
    UserPreferencesUpdateRequest,
)


class UserService:
    def __init__(self, user_repo: UserRepository, menu_repo: MenuRepository) -> None:
        self._user_repo = user_repo
        self._menu_repo = menu_repo

    async def get_preferences(self, user_id: str) -> UserPreferences:
        return await self._user_repo.get_preferences(user_id)

    async def update_preferences(self, user_id: str, payload: UserPreferencesUpdateRequest) -> UserPreferences:
        current = await self._user_repo.get_preferences(user_id)

        return await self._user_repo.upsert_preferences(
            user_id=user_id,
            favorite_hall=payload.favorite_hall or current.favorite_hall,
            ai_auto_push=current.ai_auto_push if payload.ai_auto_push is None else payload.ai_auto_push,
            pref_tags=current.pref_tags if payload.pref_tags is None else payload.pref_tags,
            allergen_tags=current.allergen_tags if payload.allergen_tags is None else payload.allergen_tags,
        )

    async def get_notification_settings(self, user_id: str) -> NotificationSettings:
        return await self._user_repo.get_notification_settings(user_id)

    async def update_notification_settings(
        self,
        user_id: str,
        payload: NotificationSettingsUpdateRequest,
    ) -> NotificationSettings:
        current = await self._user_repo.get_notification_settings(user_id)
        times = payload.times or current.times

        return await self._user_repo.upsert_notification_settings(
            user_id=user_id,
            allow_notifications=(
                current.allow_notifications
                if payload.allow_notifications is None
                else payload.allow_notifications
            ),
            breakfast_time=times.breakfast,
            lunch_time=times.lunch,
            dinner_time=times.dinner,
        )

    async def get_favorites(self, user_id: str) -> FavoritesResponse:
        return await self._user_repo.get_favorites(user_id)

    async def replace_favorites(self, user_id: str, menu_item_ids: list[str]) -> FavoritesResponse:
        if not menu_item_ids:
            return await self._user_repo.replace_favorites(user_id, [])

        existing_items = await self._menu_repo.list_menu_items_by_ids(menu_item_ids)
        existing_ids = {item.id for item in existing_items}
        unknown_ids = [item_id for item_id in menu_item_ids if item_id not in existing_ids]
        if unknown_ids:
            raise ValueError(f"Unknown menu_item_ids: {', '.join(unknown_ids)}")

        return await self._user_repo.replace_favorites(user_id, menu_item_ids)
