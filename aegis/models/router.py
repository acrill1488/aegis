from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from aegis.models.models import ModelRecord
from aegis.models.providers.base import BaseInferenceProvider
from aegis.models.registry import ModelRegistry


QUALITY_RANKS = {
    "s": 4,
    "best": 4,
    "a": 3,
    "high": 3,
    "b": 2,
    "balanced": 2,
    "medium": 2,
    "c": 1,
    "low": 1,
    "unknown": 0,
}

SPEED_RANKS = {
    "fast": 3,
    "balanced": 2,
    "medium": 2,
    "slow": 1,
    "unknown": 0,
}


class ModelRouter:
    """Select eligible model records for Model Runtime requests."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        providers: dict[str, BaseInferenceProvider] | None = None,
    ):
        self.model_registry = model_registry
        self.providers = providers or {}

    def candidates(
        self,
        task_type: str,
        enabled_only: bool = True,
    ) -> list[ModelRecord]:
        return self.model_registry.list(
            task_type=task_type,
            enabled_only=enabled_only,
        )

    def select(
        self,
        task_type: str,
        constraints: dict | None = None,
    ) -> ModelRecord | None:
        constraints = constraints or {}
        provider_health = self._provider_health()
        records = [
            record
            for record in self.candidates(task_type, enabled_only=True)
            if self._matches_constraints(record, constraints)
            and self._provider_is_selectable(record.provider, provider_health)
        ]
        if not records:
            return None
        return sorted(records, key=self._sort_key)[0]

    def _matches_constraints(
        self,
        record: ModelRecord,
        constraints: dict[str, Any],
    ) -> bool:
        provider = constraints.get("provider")
        if provider is not None and record.provider != str(provider):
            return False

        min_context_window = constraints.get(
            "min_context_window",
            constraints.get("minimum_context_window"),
        )
        if min_context_window is not None:
            if record.context_window is None:
                return False
            if record.context_window < int(min_context_window):
                return False

        quality_tier = constraints.get("quality_tier")
        if quality_tier is not None:
            if self._rank(record.quality_tier, QUALITY_RANKS) < self._rank(
                quality_tier,
                QUALITY_RANKS,
            ):
                return False

        speed_tier = constraints.get("speed_tier")
        if speed_tier is not None:
            if self._rank(record.speed_tier, SPEED_RANKS) < self._rank(
                speed_tier,
                SPEED_RANKS,
            ):
                return False

        if not self._supports_modalities(
            record.input_modalities,
            constraints.get("input_modalities"),
        ):
            return False

        return self._supports_modalities(
            record.output_modalities,
            constraints.get("output_modalities"),
        )

    def _provider_health(self) -> dict[str, dict]:
        health: dict[str, dict] = {}
        for provider_id, provider in self.providers.items():
            try:
                payload = provider.health()
            except Exception as exc:
                payload = {
                    "provider_id": provider_id,
                    "status": "unhealthy",
                    "error": str(exc),
                }
            if isinstance(payload, dict):
                health[provider_id] = payload
        return health

    def _provider_is_selectable(
        self,
        provider_id: str,
        health: dict[str, dict],
    ) -> bool:
        payload = health.get(provider_id)
        if payload is None:
            return True
        return str(payload.get("status", "unknown")).lower() != "unhealthy"

    def _sort_key(self, record: ModelRecord) -> tuple[int, int, float, str]:
        return (
            -self._rank(record.quality_tier, QUALITY_RANKS),
            -self._rank(record.speed_tier, SPEED_RANKS),
            record.vram_required_gb
            if record.vram_required_gb is not None
            else float("inf"),
            record.id,
        )

    def _supports_modalities(
        self,
        supported: list[str],
        required: Any,
    ) -> bool:
        if required is None:
            return True
        required_modalities = self._as_string_list(required)
        return all(modality in supported for modality in required_modalities)

    def _as_string_list(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, Iterable):
            return [str(item) for item in value]
        return [str(value)]

    def _rank(self, value: Any, ranks: dict[str, int]) -> int:
        return ranks.get(str(value).lower(), ranks["unknown"])
