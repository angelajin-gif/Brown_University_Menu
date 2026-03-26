from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Keep list parsing under our validators so comma-separated env values
        # (common in Railway variables) won't fail JSON pre-decoding.
        enable_decoding=False,
    )

    app_name: str = "Canteen AI Backend"
    environment: str = "development"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000
    api_v1_prefix: str = "/api/v1"

    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    cors_allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    cors_allowed_headers: list[str] = Field(default_factory=lambda: ["Authorization", "Content-Type", "X-Requested-With"])
    cors_allow_credentials: bool = True

    supabase_db_url: str = Field(default="", description="Supabase PostgreSQL connection string")
    supabase_url: str = Field(default="", description="Supabase project URL for official SDK")
    supabase_service_role_key: str = Field(default="", description="Supabase service role key for upsert sync")
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10
    db_command_timeout_seconds: int = 30

    brown_menu_api_url: str = "https://esb-level1.brown.edu/services/oit/sys/brown-dining/v1/menus"
    menu_sync_timezone: str = "America/New_York"
    menu_sync_batch_size: int = 300
    menu_sync_only_today: bool = True

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "qwen/qwen3-next-80b-a3b-instruct:free"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_timeout_seconds: int = 60
    openrouter_http_referer: str = ""
    openrouter_title: str = "canteen-ai-backend"

    rag_top_k: int = 6
    rag_keyword_top_k: int = 6
    embedding_dimensions: int = 1536

    default_lang: str = "zh"

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: object) -> list[str]:
        return cls._parse_list_value(value)

    @field_validator("cors_allowed_methods", "cors_allowed_headers", mode="before")
    @classmethod
    def parse_cors_lists(cls, value: object) -> list[str]:
        return cls._parse_list_value(value)

    @classmethod
    def _parse_list_value(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = []
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return []

    @field_validator("supabase_db_url")
    @classmethod
    def validate_supabase_db_url(cls, value: str) -> str:
        return value.strip()

    @field_validator("supabase_url", "supabase_service_role_key", "brown_menu_api_url")
    @classmethod
    def validate_trimmed_fields(cls, value: str) -> str:
        return value.strip()

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
