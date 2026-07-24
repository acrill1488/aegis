"""BGE-M3 provider health model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderHealth:
    provider: str = "bge-m3"
    status: str = "package missing"
    available: bool = False
    device: str = "unavailable"
    message: str = ""
    model_cached: bool | None = None
    model_loaded: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider, "status": self.status, "available": self.available,
            "device": self.device, "message": self.message, "model_cached": self.model_cached,
            "model_loaded": self.model_loaded, "metadata": dict(self.metadata),
        }

