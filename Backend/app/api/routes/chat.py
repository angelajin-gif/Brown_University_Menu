from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_chat_service
from app.models.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.openrouter_service import OpenRouterError

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    async def event_stream():
        try:
            async for token in chat_service.stream_chat(payload.message):
                data = json.dumps(
                    {"type": "token", "delta": token},
                    ensure_ascii=False,
                )
                yield f"data: {data}\n\n"
        except (OpenRouterError, ValueError) as error:
            data = json.dumps(
                {"type": "error", "message": str(error)},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {data}\n\n"
            return
        except Exception as error:  # noqa: BLE001 - keep stream protocol stable on unexpected errors.
            data = json.dumps(
                {"type": "error", "message": f"Unexpected chat stream error: {error}"},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {data}\n\n"
            return

        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
