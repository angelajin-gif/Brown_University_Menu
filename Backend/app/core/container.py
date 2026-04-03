from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.db.postgres import Database
from app.db.repositories.menu_repository import MenuRepository
from app.db.repositories.rag_repository import RagRepository
from app.db.repositories.user_repository import UserRepository
from app.services.chat_service import ChatService
from app.services.custom_station_service import CustomStationService
from app.services.embedding_service import EmbeddingService
from app.services.insight_service import InsightService
from app.services.menu_service import MenuService
from app.services.openrouter_service import OpenRouterService
from app.services.rag_service import RagService
from app.services.user_service import UserService


@dataclass
class AppContainer:
    settings: Settings
    db: Database
    openrouter: OpenRouterService
    menu_repository: MenuRepository
    user_repository: UserRepository
    rag_repository: RagRepository
    embedding_service: EmbeddingService
    rag_service: RagService
    menu_service: MenuService
    user_service: UserService
    insight_service: InsightService
    chat_service: ChatService
    custom_station_service: CustomStationService
