from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_menu_service, get_settings
from app.core.config import Settings
from app.models.enums import HallId, MealSlot
from app.models.menu import MenuItem, MenuListResponse
from app.services.menu_service import MenuService

router = APIRouter(prefix="/menus", tags=["menus"])


@router.get("", response_model=MenuListResponse)
async def list_menus(
    meal_slot: MealSlot | None = Query(default=None),
    hall_id: HallId | None = Query(default=None),
    query: str | None = Query(default=None, max_length=120),
    service_date: date | None = Query(default=None),
    user_id: str | None = Query(default=None),
    respect_user_allergens: bool = Query(default=True),
    menu_service: MenuService = Depends(get_menu_service),
    settings: Settings = Depends(get_settings),
) -> MenuListResponse:
    if service_date is None:
        service_date = datetime.now(ZoneInfo(settings.menu_sync_timezone)).date()

    items = await menu_service.list_menu_items(
        user_id=user_id,
        meal_slot=meal_slot,
        hall_id=hall_id,
        query=query,
        service_date=service_date,
        respect_user_allergens=respect_user_allergens,
    )
    return MenuListResponse(items=items, total=len(items))


@router.get("/{item_id}", response_model=MenuItem)
async def get_menu_item(
    item_id: str,
    menu_service: MenuService = Depends(get_menu_service),
) -> MenuItem:
    item = await menu_service.get_menu_item(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"menu item '{item_id}' not found",
        )
    return item
