from __future__ import annotations

from app.core.config import Settings
from app.services.openrouter_service import OpenRouterService


class EmbeddingService:
    def __init__(self, openrouter: OpenRouterService, settings: Settings) -> None:
        self._openrouter = openrouter
        self._settings = settings

    async def embed_text(self, text: str) -> list[float]:
        embeddings = await self._openrouter.create_embeddings([text])
        if not embeddings:
            raise ValueError("No embedding returned by provider.")
        embedding = embeddings[0]
        self._validate_dimensions(embedding)
        return embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = await self._openrouter.create_embeddings(texts)
        for embedding in embeddings:
            self._validate_dimensions(embedding)
        return embeddings

    def _validate_dimensions(self, embedding: list[float]) -> None:
        expected = self._settings.embedding_dimensions
        if len(embedding) != expected:
            raise ValueError(
                f"Embedding dimension mismatch. Expected {expected}, got {len(embedding)}"
            )
