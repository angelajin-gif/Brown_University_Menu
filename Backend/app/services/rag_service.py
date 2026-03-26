from __future__ import annotations

from collections.abc import Sequence

from app.core.config import Settings
from app.db.repositories.rag_repository import RagRepository
from app.models.enums import SourceType
from app.models.rag import KnowledgeChunkInput, KnowledgeChunkResponse
from app.services.embedding_service import EmbeddingService


class RagService:
    def __init__(
        self,
        rag_repo: RagRepository,
        embedding_service: EmbeddingService,
        settings: Settings,
    ) -> None:
        self._rag_repo = rag_repo
        self._embedding_service = embedding_service
        self._settings = settings

    async def upsert_knowledge_chunks(self, chunks: Sequence[KnowledgeChunkInput]) -> int:
        if not chunks:
            return 0

        grouped: dict[SourceType, list[KnowledgeChunkInput]] = {}
        for chunk in chunks:
            grouped.setdefault(chunk.source_type, []).append(chunk)

        for source_type, source_chunks in grouped.items():
            contents = [chunk.content for chunk in source_chunks]
            embeddings = await self._embedding_service.embed_texts(contents)
            await self._rag_repo.upsert_chunks(
                source_type=source_type,
                source_ids=[chunk.source_id for chunk in source_chunks],
                contents=contents,
                metadatas=[chunk.metadata for chunk in source_chunks],
                embeddings=embeddings,
            )

        return len(chunks)

    async def hybrid_search(self, query: str, top_k: int | None = None) -> list[KnowledgeChunkResponse]:
        if not query.strip():
            return []

        limit = top_k or self._settings.rag_top_k
        embedding = await self._embedding_service.embed_text(query)

        vector_hits = await self._rag_repo.search_by_vector(
            embedding=embedding,
            top_k=limit,
        )
        keyword_hits = await self._rag_repo.search_by_keywords(
            query=query,
            top_k=self._settings.rag_keyword_top_k,
        )

        merged: dict[str, KnowledgeChunkResponse] = {}

        for chunk in vector_hits:
            merged[chunk.id] = chunk.model_copy(update={"score": chunk.score * 0.7})

        for chunk in keyword_hits:
            weighted = chunk.score * 0.3
            if chunk.id in merged:
                current = merged[chunk.id]
                merged[chunk.id] = current.model_copy(update={"score": current.score + weighted})
            else:
                merged[chunk.id] = chunk.model_copy(update={"score": weighted})

        ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
        return ranked[:limit]

    @staticmethod
    def render_context(chunks: Sequence[KnowledgeChunkResponse]) -> str:
        if not chunks:
            return "无可用知识库上下文。"

        lines: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            source = f"{chunk.source_type.value}:{chunk.source_id}"
            lines.append(f"[{index}] ({source}) {chunk.content}")
        return "\n".join(lines)
