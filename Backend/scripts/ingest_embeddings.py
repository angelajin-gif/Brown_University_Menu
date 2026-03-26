from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.postgres import Database
from app.db.repositories.rag_repository import RagRepository
from app.models.enums import SourceType
from app.models.rag import KnowledgeChunkInput
from app.services.embedding_service import EmbeddingService
from app.services.openrouter_service import OpenRouterService
from app.services.rag_service import RagService


async def run() -> None:
    settings = get_settings()
    db = Database(settings)
    await db.connect()

    openrouter = OpenRouterService(settings)
    rag_repo = RagRepository(db)
    embedding_service = EmbeddingService(openrouter, settings)
    rag_service = RagService(rag_repo, embedding_service, settings)

    try:
        rows = await db.fetch(
            """
            SELECT source_type, source_id, content, metadata
            FROM knowledge_chunks
            WHERE embedding IS NULL
            ORDER BY source_type, source_id;
            """
        )

        chunks = [
            KnowledgeChunkInput(
                source_type=SourceType(row["source_type"]),
                source_id=row["source_id"],
                content=row["content"],
                metadata=row["metadata"] or {},
            )
            for row in rows
        ]

        total = await rag_service.upsert_knowledge_chunks(chunks)
        print(f"embedded and upserted {total} chunks")
    finally:
        await openrouter.close()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
