from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from aegis.models.models import ModelRecord
from aegis.models.output_filter import IDENTITY_FALLBACK_TEXT
from aegis.models.output_filter import clean_model_output
from aegis.models.prompt_profiles import PromptProfileManager
from aegis.models.providers.base import BaseInferenceProvider
from aegis.models.registry import ModelRegistry
from aegis.models.requests import ModelRequest
from aegis.models.results import InferenceResult
from aegis.models.router import ModelRouter


class ModelRuntime:
    def __init__(
        self,
        model_registry: ModelRegistry,
        providers: dict[str, BaseInferenceProvider],
    ):
        self.model_registry = model_registry
        self.providers = providers
        self.router = ModelRouter(
            model_registry=self.model_registry,
            providers=self.providers,
        )
        self.prompt_profiles = PromptProfileManager()

    def route(
        self,
        request: ModelRequest | str,
        constraints: dict | None = None,
    ) -> ModelRecord | None:
        if isinstance(request, ModelRequest):
            return self.router.select(request.task_type, request.constraints)
        return self.router.select(request, constraints)

    def generate(self, request: ModelRequest) -> InferenceResult:
        shortcut = self._shortcut_response(request)
        if shortcut is not None:
            return InferenceResult(
                success=True,
                task_type=request.task_type,
                output={"text": shortcut},
            )

        model = self.router.select(request.task_type, request.constraints)
        if model is None:
            return InferenceResult(
                success=False,
                task_type=request.task_type,
                error=f"model_unavailable: {request.task_type}",
            )

        provider = self.providers.get(model.provider)
        if provider is None:
            return InferenceResult(
                success=False,
                task_type=request.task_type,
                model_id=model.id,
                provider_id=model.provider,
                error=f"provider_unavailable: {model.provider}",
            )

        prepared_request = self._prepare_request(request)
        result = provider.generate(model.model_ref, prepared_request)
        result.model_id = result.model_id or model.id
        result.provider_id = result.provider_id or provider.provider_id
        if result.success and "text" in result.output:
            result.output["text"] = clean_model_output(str(result.output.get("text", "")))
        return result

    def _prepare_request(self, request: ModelRequest) -> ModelRequest:
        input_payload = dict(request.input)
        profile = request.prompt_profile

        prompt = input_payload.get("prompt")
        if prompt is not None:
            input_payload["prompt"] = self.prompt_profiles.build_prompt(
                request.task_type,
                str(prompt),
                profile=profile,
            )
            return replace(request, input=input_payload)

        messages = input_payload.get("messages")
        if isinstance(messages, list):
            input_payload["messages"] = self._with_profile_message(
                request.task_type,
                messages,
                profile,
            )
            return replace(request, input=input_payload)

        return request

    def _with_profile_message(
        self,
        task_type: str,
        messages: list[Any],
        profile: str | None,
    ) -> list[Any]:
        instruction = self.prompt_profiles.instruction_text(task_type, profile)
        profile_message = {"role": "system", "content": instruction}
        return [profile_message, *messages]

    def _shortcut_response(self, request: ModelRequest) -> str | None:
        prompt = request.input.get("prompt")
        if prompt is None:
            return None
        normalized = self._normalize_identity_prompt(str(prompt))
        if len(normalized.split()) > 5:
            return None
        identity_phrases = (
            "кто ты",
            "что ты",
            "как тебя зовут",
        )
        return (
            IDENTITY_FALLBACK_TEXT
            if any(phrase in normalized for phrase in identity_phrases)
            else None
        )

    def _normalize_identity_prompt(self, prompt: str) -> str:
        normalized = prompt.lower().replace("ё", "е")
        normalized = re.sub(r"[^\w\s]+", " ", normalized, flags=re.UNICODE)
        return re.sub(r"\s+", " ", normalized).strip()
