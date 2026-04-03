from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import date
from typing import Any

from app.db.postgres import Database
from app.models.enums import SourceType
from app.models.rag import KnowledgeChunkResponse


class RagRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    @staticmethod
    def _to_vector_literal(embedding: Sequence[float]) -> str:
        return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"

    @staticmethod
    def _row_to_chunk(row: dict) -> KnowledgeChunkResponse:
        return KnowledgeChunkResponse(
            id=str(row["id"]),
            source_type=SourceType(row["source_type"]),
            source_id=row["source_id"],
            content=row["content"],
            metadata=row.get("metadata") or {},
            score=float(row["score"]),
        )

    async def upsert_chunks(
        self,
        source_type: SourceType,
        source_ids: Sequence[str],
        contents: Sequence[str],
        metadatas: Sequence[dict],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if not source_ids:
            return

        sql = """
            INSERT INTO knowledge_chunks (
                source_type,
                source_id,
                content,
                metadata,
                embedding
            )
            VALUES ($1, $2, $3, $4::jsonb, $5::vector)
            ON CONFLICT (source_type, source_id)
            DO UPDATE SET
                content = EXCLUDED.content,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                updated_at = NOW();
        """

        args = [
            (
                source_type.value,
                source_id,
                content,
                json.dumps(metadata, ensure_ascii=False),
                self._to_vector_literal(embedding),
            )
            for source_id, content, metadata, embedding in zip(
                source_ids,
                contents,
                metadatas,
                embeddings,
                strict=True,
            )
        ]

        async with self._db.pool.acquire() as connection:
            async with connection.transaction():
                await connection.executemany(sql, args)

    async def search_by_vector(
        self,
        embedding: Sequence[float],
        top_k: int,
    ) -> list[KnowledgeChunkResponse]:
        sql = """
            SELECT
                id,
                source_type,
                source_id,
                content,
                metadata,
                GREATEST(0, 1 - (embedding <=> $1::vector)) AS score
            FROM knowledge_chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2;
        """
        rows = await self._db.fetch(sql, self._to_vector_literal(embedding), top_k)
        return [self._row_to_chunk(dict(row)) for row in rows]

    async def search_by_keywords(self, query: str, top_k: int) -> list[KnowledgeChunkResponse]:
        tokens = self._extract_tokens(query)
        if not tokens:
            return []

        patterns = [f"%{token}%" for token in tokens]
        sql = """
            SELECT
                id,
                source_type,
                source_id,
                content,
                metadata,
                (
                    SELECT COALESCE(SUM(CASE WHEN content ILIKE pattern THEN 1 ELSE 0 END), 0)
                    FROM unnest($1::text[]) AS pattern
                )::float AS score
            FROM knowledge_chunks
            WHERE EXISTS (
                SELECT 1
                FROM unnest($1::text[]) AS pattern
                WHERE content ILIKE pattern
            )
            ORDER BY score DESC, updated_at DESC
            LIMIT $2;
        """
        rows = await self._db.fetch(sql, patterns, top_k)
        return [self._row_to_chunk(dict(row)) for row in rows]

    async def search_daily_menu_items_by_rpc(
        self,
        embedding: Sequence[float],
        service_date: date,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT
                menu_item_id,
                similarity,
                name_en,
                name_zh,
                description,
                calories,
                protein,
                carbs,
                fat,
                tags,
                allergens,
                hall_id,
                meal_slot,
                station_name,
                meal_name,
                nutrition_available,
                nutrition_item_id
            FROM match_daily_menu_items($1::vector, $2::date, $3::int);
        """
        rows = await self._db.fetch(
            sql,
            self._to_vector_literal(embedding),
            service_date,
            top_k,
        )
        return [dict(row) for row in rows]

    @staticmethod
    def _extract_tokens(query: str) -> list[str]:
        if not query.strip():
            return []
        raw = re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]{2,}", query.lower())
        seen: set[str] = set()
        ordered: list[str] = []
        for token in raw:
            if token in seen:
                continue
            seen.add(token)
            ordered.append(token)
        return ordered[:8]
