"""OCR Platform diagnostics."""

from __future__ import annotations

from typing import Any

from .registry import OCRRegistry, provider_name


class OCRDoctor:
    """Builds a provider-neutral OCR Platform health report."""

    def __init__(self, registry: OCRRegistry):
        self.registry = registry

    def report(self, verbose: bool = False) -> dict[str, Any]:
        providers = [
            {
                "name": provider_name(provider),
                "available": provider.available(),
                "default": provider_name(provider) == self.registry.default(),
                "health": provider.health(),
                "capabilities": provider.capabilities(),
                "supported_formats": provider.supported_formats(),
                "doctor": provider.doctor(verbose=verbose)
                if hasattr(provider, "doctor")
                else {},
            }
            for provider in self.registry.providers()
        ]
        available = [provider["name"] for provider in providers if provider["available"]]
        unlimited = next((provider for provider in providers if provider["name"] == "unlimited"), None)
        unlimited_doctor = unlimited.get("doctor", {}) if unlimited else {}
        states = unlimited_doctor.get("states", {}) if isinstance(unlimited_doctor, dict) else {}
        service_alive = bool(states.get("service_alive")) if states else "unlimited" in available
        recognition_ready = bool(states.get("recognition_ready")) if states else False
        overall = "PRODUCTION READY" if service_alive and recognition_ready else "FOUNDATION READY"
        if service_alive and not recognition_ready:
            overall = "SERVICE READY / INFERENCE NOT VERIFIED"
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
            "overall": overall,
            "models_checked": bool(unlimited),
            "states": states,
        }
