from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.chat import router as chat_router
from app.api.routes.custom_station import router as custom_station_router
from app.api.routes.favorite import router as favorite_router
from app.api.routes.health import router as health_router
from app.api.routes.insights import router as insights_router
from app.api.routes.menu import router as menu_router
from app.api.routes.preferences import router as preferences_router
from app.api.routes.rag import router as rag_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(menu_router)
api_router.include_router(favorite_router)
api_router.include_router(preferences_router)
api_router.include_router(insights_router)
api_router.include_router(rag_router)
api_router.include_router(chat_router)
api_router.include_router(custom_station_router)
