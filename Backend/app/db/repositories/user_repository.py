from __future__ import annotations

from collections.abc import Sequence

from app.db.postgres import Database
from app.models.enums import AllergenTag, DietaryTag, HallId
from app.models.preferences import (
    FavoritesResponse,
    NotificationSettings,
    NotificationTimes,
    UserPreferences,
)


class UserRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def ensure_user(self, user_id: str) -> None:
        sql = """
            INSERT INTO users (id)
            VALUES ($1)
            ON CONFLICT (id) DO NOTHING;
        """
        await self._db.execute(sql, user_id)

    async def get_preferences(self, user_id: str) -> UserPreferences:
        await self.ensure_user(user_id)

        sql = """
            SELECT
                user_id,
                favorite_hall,
                ai_auto_push,
                pref_tags,
                allergen_tags
            FROM user_preferences
            WHERE user_id = $1;
        """
        row = await self._db.fetchrow(sql, user_id)
        if row is None:
            return UserPreferences(
                user_id=user_id,
                favorite_hall=HallId.hall1,
                ai_auto_push=True,
                pref_tags=[],
                allergen_tags=[],
            )

        return UserPreferences(
            user_id=row["user_id"],
            favorite_hall=HallId(row["favorite_hall"]),
            ai_auto_push=bool(row["ai_auto_push"]),
            pref_tags=[DietaryTag(tag) for tag in (row["pref_tags"] or [])],
            allergen_tags=[AllergenTag(tag) for tag in (row["allergen_tags"] or [])],
        )

    async def upsert_preferences(
        self,
        user_id: str,
        favorite_hall: HallId,
        ai_auto_push: bool,
        pref_tags: Sequence[DietaryTag],
        allergen_tags: Sequence[AllergenTag],
    ) -> UserPreferences:
        await self.ensure_user(user_id)

        sql = """
            INSERT INTO user_preferences (
                user_id,
                favorite_hall,
                ai_auto_push,
                pref_tags,
                allergen_tags
            )
            VALUES ($1, $2, $3, $4::text[], $5::text[])
            ON CONFLICT (user_id)
            DO UPDATE SET
                favorite_hall = EXCLUDED.favorite_hall,
                ai_auto_push = EXCLUDED.ai_auto_push,
                pref_tags = EXCLUDED.pref_tags,
                allergen_tags = EXCLUDED.allergen_tags,
                updated_at = NOW();
        """
        await self._db.execute(
            sql,
            user_id,
            favorite_hall.value,
            ai_auto_push,
            [tag.value for tag in pref_tags],
            [tag.value for tag in allergen_tags],
        )
        return await self.get_preferences(user_id)

    async def get_notification_settings(self, user_id: str) -> NotificationSettings:
        await self.ensure_user(user_id)
        sql = """
            SELECT
                allow_notifications,
                breakfast_time,
                lunch_time,
                dinner_time
            FROM user_notification_settings
            WHERE user_id = $1;
        """
        row = await self._db.fetchrow(sql, user_id)
        if row is None:
            return NotificationSettings()

        return NotificationSettings(
            allow_notifications=bool(row["allow_notifications"]),
            times=NotificationTimes(
                breakfast=str(row["breakfast_time"])[0:5],
                lunch=str(row["lunch_time"])[0:5],
                dinner=str(row["dinner_time"])[0:5],
            ),
        )

    async def upsert_notification_settings(
        self,
        user_id: str,
        allow_notifications: bool,
        breakfast_time: str,
        lunch_time: str,
        dinner_time: str,
    ) -> NotificationSettings:
        await self.ensure_user(user_id)
        sql = """
            INSERT INTO user_notification_settings (
                user_id,
                allow_notifications,
                breakfast_time,
                lunch_time,
                dinner_time
            )
            VALUES ($1, $2, $3::time, $4::time, $5::time)
            ON CONFLICT (user_id)
            DO UPDATE SET
                allow_notifications = EXCLUDED.allow_notifications,
                breakfast_time = EXCLUDED.breakfast_time,
                lunch_time = EXCLUDED.lunch_time,
                dinner_time = EXCLUDED.dinner_time,
                updated_at = NOW();
        """
        await self._db.execute(sql, user_id, allow_notifications, breakfast_time, lunch_time, dinner_time)
        return await self.get_notification_settings(user_id)

    async def get_favorites(self, user_id: str) -> FavoritesResponse:
        await self.ensure_user(user_id)
        sql = """
            SELECT menu_item_id
            FROM user_favorites
            WHERE user_id = $1
            ORDER BY created_at ASC;
        """
        rows = await self._db.fetch(sql, user_id)
        return FavoritesResponse(user_id=user_id, menu_item_ids=[row["menu_item_id"] for row in rows])

    async def replace_favorites(self, user_id: str, menu_item_ids: Sequence[str]) -> FavoritesResponse:
        await self.ensure_user(user_id)

        async with self._db.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute("DELETE FROM user_favorites WHERE user_id = $1", user_id)
                if menu_item_ids:
                    await connection.executemany(
                        """
                        INSERT INTO user_favorites (user_id, menu_item_id)
                        VALUES ($1, $2)
                        ON CONFLICT (user_id, menu_item_id) DO NOTHING;
                        """,
                        [(user_id, item_id) for item_id in menu_item_ids],
                    )

        return await self.get_favorites(user_id)

    async def add_favorite(self, user_id: str, menu_item_id: str) -> FavoritesResponse:
        await self.ensure_user(user_id)
        sql = """
            INSERT INTO user_favorites (user_id, menu_item_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id, menu_item_id) DO NOTHING;
        """
        await self._db.execute(sql, user_id, menu_item_id)
        return await self.get_favorites(user_id)

    async def remove_favorite(self, user_id: str, menu_item_id: str) -> FavoritesResponse:
        await self.ensure_user(user_id)
        sql = """
            DELETE FROM user_favorites
            WHERE user_id = $1 AND menu_item_id = $2;
        """
        await self._db.execute(sql, user_id, menu_item_id)
        return await self.get_favorites(user_id)
