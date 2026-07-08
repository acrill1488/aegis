from __future__ import annotations

from aegis.models.models import ModelRecord
from aegis.models.providers.base import BaseInferenceProvider
from aegis.models.registry import ModelRegistry
from aegis.models.requests import ModelRequest
from aegis.models.results import InferenceResult


class ModelRuntime:
    def __init__(
        self,
        model_registry: ModelRegistry,
        providers: dict[str, BaseInferenceProvider],
    ):
        self.model_registry = model_registry
        self.providers = providers

    def route(self, task_type: str) -> ModelRecord | None:
        records = self.model_registry.list(task_type=task_type, enabled_only=True)
        return records[0] if records else None

    def generate(self, request: ModelRequest) -> InferenceResult:
        model = self.route(request.task_type)
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

        result = provider.generate(model.model_ref, request)
        result.model_id = result.model_id or model.id
        result.provider_id = result.provider_id or provider.provider_id
        return result
