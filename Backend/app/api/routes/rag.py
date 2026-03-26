from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_rag_service
from app.models.common import MessageResponse
from app.models.rag import (
    KnowledgeChunkUpsertRequest,
    RagSearchRequest,
    RagSearchResponse,
)
from app.services.openrouter_service import OpenRouterError
from app.services.rag_service import RagService

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/chunks/upsert", response_model=MessageResponse)
async def upsert_knowledge_chunks(
    payload: KnowledgeChunkUpsertRequest,
    rag_service: RagService = Depends(get_rag_service),
) -> MessageResponse:
    try:
        total = await rag_service.upsert_knowledge_chunks(payload.chunks)
    except (OpenRouterError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return MessageResponse(message=f"upserted {total} knowledge chunks")


@router.post("/search", response_model=RagSearchResponse)
async def rag_search(
    payload: RagSearchRequest,
    rag_service: RagService = Depends(get_rag_service),
) -> RagSearchResponse:
    try:
        chunks = await rag_service.hybrid_search(payload.query, top_k=payload.top_k)
    except (OpenRouterError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return RagSearchResponse(query=payload.query, chunks=chunks)
