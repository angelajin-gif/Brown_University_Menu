from __future__ import annotations

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.container import AppContainer
from app.services.insight_service import InsightService
from app.services.menu_service import MenuService
from app.services.rag_service import RagService
from app.services.user_service import UserService


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
