from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import Settings


class OpenRouterError(RuntimeError):
    pass


class OpenRouterService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.openrouter_base_url.rstrip("/"),
            timeout=settings.openrouter_timeout_seconds,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        if not self._settings.openrouter_api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is missing.")

        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        if self._settings.openrouter_http_referer:
            headers["HTTP-Referer"] = self._settings.openrouter_http_referer
        if self._settings.openrouter_title:
            headers["X-Title"] = self._settings.openrouter_title
        return headers

    async def create_embeddings(self, inputs: list[str]) -> list[list[float]]:
        if not inputs:
            return []

        payload = {
            "model": self._settings.openrouter_embedding_model,
            "input": inputs,
        }
        response = await self._client.post(
            "embeddings",
            headers=self._headers(),
            json=payload,
        )

        if response.status_code >= 400:
            raise OpenRouterError(
                f"Embedding request failed ({response.status_code}): {response.text}"
            )

        body = response.json()
        data = body.get("data")
        if not isinstance(data, list):
            raise OpenRouterError("Embedding response format is invalid.")

        embeddings: list[list[float]] = []
        for item in data:
            embedding = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(embedding, list):
                raise OpenRouterError("Embedding payload missing vector list.")
            embeddings.append([float(value) for value in embedding])
        return embeddings

    async def create_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 900,
    ) -> str:
        payload = {
            "model": self._settings.openrouter_chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await self._client.post(
            "chat/completions",
            headers=self._headers(),
            json=payload,
        )

        if response.status_code >= 400:
            raise OpenRouterError(
                f"Chat request failed ({response.status_code}): {response.text}"
            )

        body = response.json()
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenRouterError("Chat response missing choices.")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("Chat response missing text content.")

        return content.strip()

    async def create_structured_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 900,
    ) -> dict[str, Any]:
        payload = {
            "model": self._settings.openrouter_chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        response = await self._client.post(
            "chat/completions",
            headers=self._headers(),
            json=payload,
        )

        if response.status_code >= 400:
            # Some models do not support response_format, fallback to plain text json prompt.
            payload.pop("response_format", None)
            fallback_response = await self._client.post(
                "chat/completions",
                headers=self._headers(),
                json=payload,
            )
            if fallback_response.status_code >= 400:
                raise OpenRouterError(
                    f"Structured chat failed ({fallback_response.status_code}): {fallback_response.text}"
                )
            raw_content = self._extract_message_content(fallback_response.json())
            return self._parse_json_content(raw_content)

        raw_content = self._extract_message_content(response.json())
        return self._parse_json_content(raw_content)

    @staticmethod
    def _extract_message_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenRouterError("Chat response missing choices.")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text", "")))
            content = "\n".join(part for part in text_parts if part)
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("Chat response missing text content.")
        return content.strip()

    @staticmethod
    def _parse_json_content(content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise OpenRouterError("Model did not return valid JSON.")

        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise OpenRouterError("Model JSON parsing failed.") from error

        if not isinstance(parsed, dict):
            raise OpenRouterError("Model JSON root must be an object.")
        return parsed
