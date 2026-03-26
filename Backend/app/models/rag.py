from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import SourceType


class KnowledgeChunkInput(BaseModel):
    source_type: SourceType
    source_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunkUpsertRequest(BaseModel):
    chunks: list[KnowledgeChunkInput] = Field(min_length=1)


class KnowledgeChunkResponse(BaseModel):
    id: str
    source_type: SourceType
    source_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=6, ge=1, le=20)


class RagSearchResponse(BaseModel):
    query: str
    chunks: list[KnowledgeChunkResponse]
