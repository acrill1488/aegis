from __future__ import annotations

from aegis.models.requests import ModelRequest
from aegis.models.results import InferenceResult


class BaseInferenceProvider:
    provider_id: str = "base"

    def generate(self, model_ref: str, request: ModelRequest) -> InferenceResult:
        return InferenceResult(
            success=False,
            task_type=request.task_type,
            provider_id=self.provider_id,
            error="not_implemented",
        )

    def health(self) -> dict:
        return {"provider_id": self.provider_id, "status": "unknown"}

    def list_models(self) -> list[str]:
        return []
