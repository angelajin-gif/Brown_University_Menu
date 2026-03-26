from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from app.core.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool is not initialized.")
        return self._pool

    async def connect(self) -> None:
        if self._pool is not None:
            return

        async with self._lock:
            if self._pool is not None:
                return
            if not self._settings.supabase_db_url:
                raise RuntimeError("SUPABASE_DB_URL is required.")

            self._pool = await asyncpg.create_pool(
                dsn=self._settings.supabase_db_url,
                min_size=self._settings.db_pool_min_size,
                max_size=self._settings.db_pool_max_size,
                command_timeout=self._settings.db_command_timeout_seconds,
            )

    async def disconnect(self) -> None:
        if self._pool is None:
            return

        async with self._lock:
            if self._pool is None:
                return
            await self._pool.close()
            self._pool = None

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def executemany(self, query: str, args: list[tuple[Any, ...]]) -> None:
        async with self.pool.acquire() as connection:
            await connection.executemany(query, args)
