"""OCR Platform foundation diagnostics."""

from __future__ import annotations

from typing import Any

from .registry import OCRRegistry, provider_name


class OCRDoctor:
    """Builds a provider-neutral OCR Platform health report."""

    def __init__(self, registry: OCRRegistry):
        self.registry = registry

    def report(self) -> dict[str, Any]:
        providers = [
            {
                "name": provider_name(provider),
                "available": provider.available(),
                "default": provider_name(provider) == self.registry.default(),
                "health": provider.health(),
                "capabilities": provider.capabilities(),
                "supported_formats": provider.supported_formats(),
            }
            for provider in self.registry.providers()
        ]
        available = [provider["name"] for provider in providers if provider["available"]]
        return {
            "platform": "OCR Platform",
            "providers": providers,
            "available": available,
            "capabilities": {
                provider["name"]: provider["capabilities"] for provider in providers
            },
            "supported_formats": {
                provider["name"]: provider["supported_formats"] for provider in providers
            },
            "default_provider": self.registry.default(),
            "overall": "FOUNDATION READY",
            "models_checked": False,
        }
