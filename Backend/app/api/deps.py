from __future__ import annotations

import asyncio
from threading import Lock

from fastapi import Depends, Request
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from app.core.config import Settings
from app.core.container import AppContainer
from app.services.custom_station_service import CustomStationService
from app.services.chat_service import ChatService
from app.services.insight_service import InsightService
from app.services.menu_service import MenuService
from app.services.rag_service import RagService
from app.services.user_service import UserService

_bearer_scheme = HTTPBearer(auto_error=False)
_auth_client: Client | None = None
_auth_client_lock = Lock()


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_menu_service(container: AppContainer = Depends(get_container)) -> MenuService:
    return container.menu_service


def get_user_service(container: AppContainer = Depends(get_container)) -> UserService:
    return container.user_service


def get_rag_service(container: AppContainer = Depends(get_container)) -> RagService:
    return container.rag_service


def get_insight_service(container: AppContainer = Depends(get_container)) -> InsightService:
    return container.insight_service


def get_chat_service(container: AppContainer = Depends(get_container)) -> ChatService:
    return container.chat_service


def get_custom_station_service(
    container: AppContainer = Depends(get_container),
) -> CustomStationService:
    return container.custom_station_service


def _get_auth_client(settings: Settings) -> Client:
    global _auth_client
    if _auth_client is not None:
        return _auth_client

    with _auth_client_lock:
        if _auth_client is not None:
            return _auth_client
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for auth")
        _auth_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _auth_client


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    auth_client = _get_auth_client(settings)
    try:
        auth_response = await asyncio.to_thread(auth_client.auth.get_user, token)
    except Exception as error:  # noqa: BLE001 - provider SDK raises non-uniform errors.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth token",
        ) from error

    user = getattr(auth_response, "user", None)
    user_id = getattr(user, "id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth token",
        )

    return str(user_id)
