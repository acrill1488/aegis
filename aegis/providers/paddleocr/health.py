"""PaddleOCR health states and result model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderHealth:
    provider: str = "paddleocr"
    status: str = "package missing"
    available: bool = False
    device: str = "unavailable"
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "available": self.available,
            "device": self.device,
            "message": self.message,
            "metadata": dict(self.metadata),
        }

