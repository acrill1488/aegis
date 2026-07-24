from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from aegis.config.runtime_config import get_runtime_profile
from aegis.config.services import get_service_base_url
from aegis.models.providers.base import BaseInferenceProvider
from aegis.models.requests import ModelRequest
from aegis.models.results import InferenceResult


class OllamaProvider(BaseInferenceProvider):
    provider_id = "ollama"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or self._base_url_from_config()).rstrip("/")

    def list_models(self) -> list[str]:
        response = httpx.get(
            f"{self.base_url}/api/tags",
            timeout=30.0,
            trust_env=False,
        )
        response.raise_for_status()
        data = response.json()
        return [
            model["name"]
            for model in data.get("models", [])
            if isinstance(model, dict) and "name" in model
        ]

    def health(self) -> dict:
        started_at = perf_counter()
        try:
            models = self.list_models()
        except Exception as exc:
            return {
                "provider_id": self.provider_id,
                "status": "unhealthy",
                "base_url": self.base_url,
                "error": str(exc),
                "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            }
        return {
            "provider_id": self.provider_id,
            "status": "healthy",
            "base_url": self.base_url,
            "available_models": models,
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
        }

    def generate(self, model_ref: str, request: ModelRequest) -> InferenceResult:
        started_at = perf_counter()
        try:
            prompt = self._prompt_from_request(request)
            options = request.constraints.get("options", {})
            if not isinstance(options, dict):
                options = {}

            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model_ref,
                    "prompt": prompt,
                    "stream": False,
                    "options": options,
                },
                timeout=request.timeout_ms / 1000,
                trust_env=False,
            )
            response.raise_for_status()
            data = response.json()
            return InferenceResult(
                success=True,
                task_type=request.task_type,
                provider_id=self.provider_id,
                output={"text": data.get("response", "")},
                latency_ms=round((perf_counter() - started_at) * 1000, 2),
                metadata={"raw_done": data.get("done")},
            )
        except Exception as exc:
            return InferenceResult(
                success=False,
                task_type=request.task_type,
                provider_id=self.provider_id,
                error=str(exc),
                latency_ms=round((perf_counter() - started_at) * 1000, 2),
            )

    def _base_url_from_config(self) -> str:
        try:
            profile = get_runtime_profile()
        except (FileNotFoundError, ValueError):
            profile = {}
        return get_service_base_url("ollama", explicit=profile.get("base_url"))

    def _prompt_from_request(self, request: ModelRequest) -> str:
        prompt = request.input.get("prompt")
        if prompt is not None:
            return str(prompt)

        messages = request.input.get("messages")
        if isinstance(messages, list):
            return self._messages_to_prompt(messages)

        return ""

    def _messages_to_prompt(self, messages: list[Any]) -> str:
        parts: list[str] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role", "user"))
            content = str(message.get("content", ""))
            if content:
                parts.append(f"{role}: {content}")
        return "\n".join(parts)
