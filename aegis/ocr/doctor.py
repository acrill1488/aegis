"""OCR Platform diagnostics."""

from __future__ import annotations

from typing import Any

from .registry import OCRRegistry, provider_name


class OCRDoctor:
    """Builds a provider-neutral OCR Platform health report."""

    def __init__(self, registry: OCRRegistry):
        self.registry = registry

    def report(
        self,
        verbose: bool = False,
        provider: str | None = None,
    ) -> dict[str, Any]:
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
        report = {
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
        if provider is not None:
            selected_instance = self.registry.provider(provider)
            selected_name = provider_name(selected_instance)
            selected = next(item for item in providers if item["name"] == selected_name)
            health = selected.get("health", {})
            available = bool(selected["available"])
            report["selected_provider"] = {
                "id": selected_name,
                "overall": "READY" if available else "NOT READY",
                "available": available,
                "device": health.get("device", "unavailable"),
                "status": health.get("status", "unknown"),
                "reason": None if available else health.get("status", "unavailable"),
                "message": health.get("message") or health.get("error"),
                "states": selected.get("doctor", {}).get("states", {}),
            }
        return report
