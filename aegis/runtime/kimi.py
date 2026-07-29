"""Kimi runtime backed by Moonshot's OpenAI-compatible HTTP API."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
import json
import os
from typing import Any

import httpx

from .base import RuntimeProvider


DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"
DEFAULT_MODEL = "kimi-k3"


class KimiRuntimeProvider(RuntimeProvider):
    """Direct Kimi runtime with no routing, fallback, or retry behavior."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("AEGIS_KIMI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("AEGIS_KIMI_API_KEY")
        self.default_model = model or os.getenv("AEGIS_KIMI_MODEL") or DEFAULT_MODEL
        self.reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else os.getenv("AEGIS_KIMI_REASONING_EFFORT")
        )
        self.timeout = timeout

    def health(self) -> dict[str, bool | None]:
        status: dict[str, bool | None] = {
            "configured": bool(self.api_key and self.base_url and self.default_model),
            "reachable": False,
            "authenticated": False,
            "available": False,
            "quota": None,
            "rate_limited": False,
            "overloaded": False,
        }
        if not status["configured"]:
            return status

        try:
            response = httpx.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=self.timeout,
                trust_env=False,
            )
        except httpx.RequestError:
            return status

        status["reachable"] = True
        status_code = response.status_code
        error = self._error_details(response)
        is_quota_error = self._is_quota_error(status_code, error)
        status["authenticated"] = status_code not in {401, 403}
        status["quota"] = False if is_quota_error else (True if status_code == 200 else None)
        status["rate_limited"] = status_code == 429 and not is_quota_error
        status["overloaded"] = status_code in {503, 529} or "overload" in error.lower()
        status["available"] = status_code == 200
        return status

    def is_available(self) -> bool:
        return bool(self.health()["available"])

    def list_models(self) -> list[str]:
        self._require_api_key()
        response = httpx.get(
            f"{self.base_url}/models",
            headers=self._headers(),
            timeout=self.timeout,
            trust_env=False,
        )
        response.raise_for_status()
        data = response.json()
        return [
            item["id"]
            for item in data.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]

    def chat(
        self,
        prompt: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        messages: Iterable[dict[str, Any]] | None = None,
    ) -> str:
        self._require_api_key()
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=self._chat_payload(
                prompt=prompt,
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            ),
            timeout=timeout or self.timeout,
            trust_env=False,
        )
        response.raise_for_status()
        data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Kimi returned an invalid chat completion response") from exc

    def stream_chat(
        self,
        prompt: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        messages: Iterable[dict[str, Any]] | None = None,
    ) -> Iterator[str]:
        self._require_api_key()
        with httpx.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=self._chat_payload(
                prompt=prompt,
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            ),
            timeout=timeout or self.timeout,
            trust_env=False,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                try:
                    event = json.loads(data)
                    content = event["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue
                if content:
                    yield str(content)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": "application/json",
        }

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("Kimi API key is not configured; set AEGIS_KIMI_API_KEY")

    def _chat_payload(
        self,
        *,
        prompt: str | None,
        messages: Iterable[dict[str, Any]] | None,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
    ) -> dict[str, Any]:
        if messages is None:
            if prompt is None:
                raise ValueError("prompt or messages must be provided")
            normalized_messages = [{"role": "user", "content": prompt}]
        else:
            normalized_messages = [dict(message) for message in messages]
            if not normalized_messages:
                raise ValueError("messages must not be empty")
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": normalized_messages,
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        return payload

    @staticmethod
    def _error_details(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        return json.dumps(error, ensure_ascii=False) if not isinstance(error, str) else error

    @staticmethod
    def _is_quota_error(status_code: int, details: str) -> bool:
        normalized = details.lower().replace("-", "_").replace(" ", "_")
        return status_code == 402 or any(
            marker in normalized
            for marker in ("insufficient_quota", "quota_exceeded", "exceeded_quota")
        )


KimiRuntime = KimiRuntimeProvider
