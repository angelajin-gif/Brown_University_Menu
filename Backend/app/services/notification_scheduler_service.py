from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import Settings
from app.db.postgres import Database
from app.models.enums import MealSlot
from app.services.push_service import PushPayload, PushService

logger = logging.getLogger(__name__)


MEAL_TIME_COLUMN_BY_SLOT: dict[MealSlot, str] = {
    MealSlot.breakfast: "breakfast_time",
    MealSlot.lunch: "lunch_time",
    MealSlot.dinner: "dinner_time",
}


@dataclass(frozen=True)
class CandidateItem:
    id: str
    name_en: str
    meal_slot: str


class NotificationSchedulerService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        push_service: PushService,
    ) -> None:
        self._settings = settings
        self._db = db
        self._push_service = push_service
        self._scheduler = AsyncIOScheduler(timezone=settings.menu_sync_timezone)
        self._run_lock = asyncio.Lock()
        self._sent_cache: set[tuple[str, str, str]] = set()

    async def start(self) -> None:
        if self._scheduler.running:
            return
        self._scheduler.add_job(
            self._dispatch_due_notifications,
            trigger=CronTrigger(second=0),
            id="menu-notification-dispatch",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self._scheduler.start()
        logger.info("notification scheduler started")

    async def shutdown(self) -> None:
        if not self._scheduler.running:
            return
        self._scheduler.shutdown(wait=False)
        logger.info("notification scheduler stopped")

    async def _dispatch_due_notifications(self) -> None:
        if self._run_lock.locked():
            logger.warning("notification scheduler skipped: previous run is still in progress")
            return

        async with self._run_lock:
            now = datetime.now(ZoneInfo(self._settings.menu_sync_timezone))
            service_date = now.date()
            trigger_hhmm = now.strftime("%H:%M")
            self._prune_sent_cache(service_date.isoformat())

            for meal_slot, time_column in MEAL_TIME_COLUMN_BY_SLOT.items():
                due_user_ids = await self._list_due_user_ids(trigger_hhmm, time_column)
                if not due_user_ids:
                    continue

                for user_id in due_user_ids:
                    cache_key = (service_date.isoformat(), meal_slot.value, user_id)
                    if cache_key in self._sent_cache:
                        continue

                    try:
                        candidate, reason = await self._pick_candidate_for_user(
                            user_id=user_id,
                            service_date=service_date,
                            meal_slot=meal_slot,
                        )
                        if candidate is None or reason is None:
                            continue

                        await self._push_service.push_menu_item(
                            PushPayload(
                                user_id=user_id,
                                meal_slot=candidate.meal_slot,
                                menu_item_id=candidate.id,
                                menu_item_name=candidate.name_en,
                                reason=reason,
                            )
                        )
                        self._sent_cache.add(cache_key)
                    except Exception:  # noqa: BLE001 - keep scheduler resilient per-user.
                        logger.exception(
                            "notification dispatch failed for user_id=%s meal_slot=%s",
                            user_id,
                            meal_slot.value,
                        )

    def _prune_sent_cache(self, service_date_iso: str) -> None:
        self._sent_cache = {key for key in self._sent_cache if key[0] == service_date_iso}

    async def _list_due_user_ids(self, trigger_hhmm: str, time_column: str) -> list[str]:
        sql = f"""
            SELECT ns.user_id
            FROM user_notification_settings AS ns
            INNER JOIN users AS u
                ON u.id = ns.user_id
            WHERE ns.allow_notifications = TRUE
              AND to_char(ns.{time_column}, 'HH24:MI') = $1;
        """
        rows = await self._db.fetch(sql, trigger_hhmm)
        return [str(row["user_id"]) for row in rows]

    async def _pick_candidate_for_user(
        self,
        user_id: str,
        service_date: date,
        meal_slot: MealSlot,
    ) -> tuple[CandidateItem | None, str | None]:
        favorite_hit = await self._pick_favorite_item(user_id, service_date, meal_slot)
        if favorite_hit is not None:
            return favorite_hit, "favorite"

        preference_hit = await self._pick_preference_item(user_id, service_date, meal_slot)
        if preference_hit is not None:
            return preference_hit, "dietary_preference"

        return None, None

    async def _pick_favorite_item(
        self,
        user_id: str,
        service_date: date,
        meal_slot: MealSlot,
    ) -> CandidateItem | None:
        sql = """
            SELECT
                mi.id,
                mi.name_en,
                mi.meal_slot
            FROM user_favorites AS uf
            INNER JOIN menu_items AS mi
                ON mi.id = uf.menu_item_id
            LEFT JOIN user_preferences AS up
                ON up.user_id = uf.user_id
            WHERE uf.user_id = $1
              AND mi.is_active = TRUE
              AND mi.service_date = $2
              AND mi.meal_slot = $3
              AND NOT (mi.allergens && COALESCE(up.allergen_tags, '{}'::text[]))
            ORDER BY uf.created_at ASC, mi.id ASC
            LIMIT 1;
        """
        row = await self._db.fetchrow(sql, user_id, service_date, meal_slot.value)
        if row is None:
            return None
        return CandidateItem(
            id=str(row["id"]),
            name_en=str(row["name_en"]),
            meal_slot=str(row["meal_slot"]),
        )

    async def _pick_preference_item(
        self,
        user_id: str,
        service_date: date,
        meal_slot: MealSlot,
    ) -> CandidateItem | None:
        sql = """
            SELECT
                mi.id,
                mi.name_en,
                mi.meal_slot,
                COALESCE((
                    SELECT COUNT(*)
                    FROM unnest(mi.tags) AS tag
                    WHERE tag = ANY(COALESCE(up.pref_tags, '{}'::text[]))
                ), 0) AS pref_score,
                CASE
                    WHEN mi.hall_id = COALESCE(up.favorite_hall, 'hall1')
                    THEN 1
                    ELSE 0
                END AS hall_score
            FROM users AS u
            LEFT JOIN user_preferences AS up
                ON up.user_id = u.id
            INNER JOIN menu_items AS mi
                ON mi.is_active = TRUE
               AND mi.service_date = $2
               AND mi.meal_slot = $3
            WHERE u.id = $1
              AND NOT (mi.allergens && COALESCE(up.allergen_tags, '{}'::text[]))
            ORDER BY pref_score DESC, hall_score DESC, mi.calories ASC, mi.id ASC
            LIMIT 1;
        """
        row = await self._db.fetchrow(sql, user_id, service_date, meal_slot.value)
        if row is None:
            return None
        return CandidateItem(
            id=str(row["id"]),
            name_en=str(row["name_en"]),
            meal_slot=str(row["meal_slot"]),
        )
