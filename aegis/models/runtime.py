from __future__ import annotations

from aegis.models.models import ModelRecord
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

    def route(
        self,
        request: ModelRequest | str,
        constraints: dict | None = None,
    ) -> ModelRecord | None:
        if isinstance(request, ModelRequest):
            return self.router.select(request.task_type, request.constraints)
        return self.router.select(request, constraints)

    def generate(self, request: ModelRequest) -> InferenceResult:
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

        result = provider.generate(model.model_ref, request)
        result.model_id = result.model_id or model.id
        result.provider_id = result.provider_id or provider.provider_id
        return result
