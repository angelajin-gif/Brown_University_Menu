from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.services.brown_menu_sync_service import BrownMenuSyncService


async def run() -> None:
    settings = get_settings()
    service = BrownMenuSyncService(settings)
    try:
        result = await service.sync_menu_items()
        print(
            "sync completed:",
            f"date={result['service_date']}",
            f"locations={result['locations']}",
            f"upserted={result['upserted']}",
            f"nutrition_candidates={result['nutrition_candidates']}",
            f"nutrition_enriched={result['nutrition_enriched']}",
        )
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(run())
