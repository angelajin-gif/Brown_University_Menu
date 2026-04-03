from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user_id, get_user_service
from app.models.preferences import FavoritesResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/favorite", tags=["favorite"])


class FavoriteMutationRequest(BaseModel):
    menu_item_id: str = Field(min_length=1, max_length=200)


@router.post("", response_model=FavoritesResponse)
async def add_favorite(
    payload: FavoriteMutationRequest,
    user_id: str = Depends(get_current_user_id),
    user_service: UserService = Depends(get_user_service),
) -> FavoritesResponse:
    try:
        return await user_service.add_favorite(user_id, payload.menu_item_id.strip())
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete("/{menu_item_id}", response_model=FavoritesResponse)
async def remove_favorite(
    menu_item_id: str,
    user_id: str = Depends(get_current_user_id),
    user_service: UserService = Depends(get_user_service),
) -> FavoritesResponse:
    return await user_service.remove_favorite(user_id, menu_item_id.strip())
