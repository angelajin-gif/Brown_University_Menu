from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_custom_station_service
from app.models.custom_station import CustomStationNutritionRequest, CustomStationNutritionResponse
from app.services.custom_station_service import CustomStationService

router = APIRouter(prefix="/custom-station", tags=["custom-station"])


@router.post("/calculate", response_model=CustomStationNutritionResponse)
async def calculate_custom_station_nutrition(
    payload: CustomStationNutritionRequest,
    custom_station_service: CustomStationService = Depends(get_custom_station_service),
) -> CustomStationNutritionResponse:
    try:
        return await custom_station_service.calculate_nutrition(payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
