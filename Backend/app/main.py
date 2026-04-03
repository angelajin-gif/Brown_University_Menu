from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.container import AppContainer
from app.core.logging import configure_logging
from app.db.postgres import Database
from app.db.repositories.menu_repository import MenuRepository
from app.db.repositories.rag_repository import RagRepository
from app.db.repositories.user_repository import UserRepository
from app.services.chat_service import ChatService
from app.services.custom_station_service import CustomStationService
from app.services.embedding_service import EmbeddingService
from app.services.insight_service import InsightService
from app.services.menu_service import MenuService
from app.services.notification_scheduler_service import NotificationSchedulerService
from app.services.openrouter_service import OpenRouterService
from app.services.push_service import PushService
from app.services.rag_service import RagService
from app.services.user_service import UserService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(debug=settings.debug)

    db = Database(settings)
    await db.connect()

    openrouter = OpenRouterService(settings)

    menu_repo = MenuRepository(db)
    user_repo = UserRepository(db)
    rag_repo = RagRepository(db)

    embedding_service = EmbeddingService(openrouter, settings)
    rag_service = RagService(rag_repo, embedding_service, settings)
    menu_service = MenuService(menu_repo, user_repo)
    user_service = UserService(user_repo, menu_repo)
    custom_station_service = CustomStationService(menu_repo)
    insight_service = InsightService(user_repo, menu_repo, rag_service, openrouter)
    chat_service = ChatService(settings, menu_repo, rag_repo, embedding_service, openrouter)
    push_service = PushService()
    notification_scheduler = NotificationSchedulerService(settings, db, push_service)
    await notification_scheduler.start()

    container = AppContainer(
        settings=settings,
        db=db,
        openrouter=openrouter,
        menu_repository=menu_repo,
        user_repository=user_repo,
        rag_repository=rag_repo,
        embedding_service=embedding_service,
        rag_service=rag_service,
        menu_service=menu_service,
        user_service=user_service,
        custom_station_service=custom_station_service,
        insight_service=insight_service,
        chat_service=chat_service,
    )

    app.state.settings = settings
    app.state.container = container
    app.state.notification_scheduler = notification_scheduler

    try:
        yield
    finally:
        await notification_scheduler.shutdown()
        await openrouter.close()
        await db.disconnect()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allowed_methods,
        allow_headers=settings.cors_allowed_headers,
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
