from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_user_service
from app.models.preferences import (
    FavoritesResponse,
    FavoritesUpdateRequest,
    NotificationSettings,
    NotificationSettingsUpdateRequest,
    UserPreferences,
    UserPreferencesUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users/{user_id}", tags=["users"])


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(
    user_id: str,
    user_service: UserService = Depends(get_user_service),
) -> UserPreferences:
    return await user_service.get_preferences(user_id)


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(
    user_id: str,
    payload: UserPreferencesUpdateRequest,
    user_service: UserService = Depends(get_user_service),
) -> UserPreferences:
    return await user_service.update_preferences(user_id, payload)


@router.get("/notifications", response_model=NotificationSettings)
async def get_notifications(
    user_id: str,
    user_service: UserService = Depends(get_user_service),
) -> NotificationSettings:
    return await user_service.get_notification_settings(user_id)


@router.put("/notifications", response_model=NotificationSettings)
async def update_notifications(
    user_id: str,
    payload: NotificationSettingsUpdateRequest,
    user_service: UserService = Depends(get_user_service),
) -> NotificationSettings:
    return await user_service.update_notification_settings(user_id, payload)


@router.get("/favorites", response_model=FavoritesResponse)
async def get_favorites(
    user_id: str,
    user_service: UserService = Depends(get_user_service),
) -> FavoritesResponse:
    return await user_service.get_favorites(user_id)


@router.put("/favorites", response_model=FavoritesResponse)
async def replace_favorites(
    user_id: str,
    payload: FavoritesUpdateRequest,
    user_service: UserService = Depends(get_user_service),
) -> FavoritesResponse:
    try:
        return await user_service.replace_favorites(user_id, payload.menu_item_ids)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
