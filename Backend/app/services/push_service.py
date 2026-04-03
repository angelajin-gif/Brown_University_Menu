from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PushPayload:
    user_id: str
    meal_slot: str
    menu_item_id: str
    menu_item_name: str
    reason: str


class PushService:
    async def push_menu_item(self, payload: PushPayload) -> None:
        # TODO: replace this with the actual push provider integration.
        logger.info(
            "push_dispatch user_id=%s meal_slot=%s item_id=%s item_name=%s reason=%s",
            payload.user_id,
            payload.meal_slot,
            payload.menu_item_id,
            payload.menu_item_name,
            payload.reason,
        )
