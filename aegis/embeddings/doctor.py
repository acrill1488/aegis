"""Non-invasive embedding diagnostics."""

from __future__ import annotations

from .registry import EmbeddingRegistry


class EmbeddingDoctor:
    def __init__(self, registry: EmbeddingRegistry):
        self.registry = registry

    def report(self, provider: str | None = None) -> dict:
        selected = self.registry.resolve(provider)
        health = selected.health().as_dict()
        ready = bool(health["available"] and health["status"] in {"CPU runtime available", "GPU runtime available", "healthy"})
        return {
            "platform": "Embedding Platform",
            "overall": "READY" if ready else "DEGRADED",
            "default_provider": self.registry.default_provider,
            "selected_provider": {
                "id": selected.id,
                "overall": "READY" if ready else "NOT READY",
                **health,
            },
        }

