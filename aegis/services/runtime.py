from __future__ import annotations

from typing import Any

from aegis.serialization import to_plain

from .base import BaseService
from .models import ServiceStatus
from .registry import ServiceRegistry


class ServiceRuntime:
    def __init__(self, core: Any | None = None, registry: ServiceRegistry | None = None):
        self.core = core
        self.registry = registry or ServiceRegistry()

    def register(self, service: BaseService) -> dict:
        registered = self.registry.register(service)
        self._publish("service.registered", registered.id, {"service": registered.status_dict()})
        return registered.status_dict()

    def start(self, service_id: str) -> dict:
        service = self._require_service(service_id)
        service.status = ServiceStatus.starting
        try:
            result = service.start()
        except Exception as exc:
            service.status = ServiceStatus.failed
            self._publish(
                "service.failed",
                service_id,
                {"service": service.status_dict(), "error": str(exc), "phase": "start"},
            )
            raise
        if service.status != ServiceStatus.running:
            service.status = ServiceStatus.running
        self._publish("service.started", service_id, {"service": service.status_dict()})
        return result if isinstance(result, dict) else service.status_dict()

    def stop(self, service_id: str) -> dict:
        service = self._require_service(service_id)
        service.status = ServiceStatus.stopping
        try:
            result = service.stop()
        except Exception as exc:
            service.status = ServiceStatus.failed
            self._publish(
                "service.failed",
                service_id,
                {"service": service.status_dict(), "error": str(exc), "phase": "stop"},
            )
            raise
        if service.status != ServiceStatus.stopped:
            service.status = ServiceStatus.stopped
        self._publish("service.stopped", service_id, {"service": service.status_dict()})
        return result if isinstance(result, dict) else service.status_dict()

    def list(self) -> list[dict]:
        return [service.status_dict() for service in self.registry.list()]

    def health(self, service_id: str) -> dict:
        return self._require_service(service_id).health()

    def _require_service(self, service_id: str) -> BaseService:
        service = self.registry.get(service_id)
        if service is None:
            raise KeyError(f"Service not found: {service_id}")
        return service

    def _publish(self, event_type: str, service_id: str, payload: dict) -> None:
        events = getattr(self.core, "events", None)
        if events is None or not hasattr(events, "publish"):
            return
        try:
            events.publish(
                event_type,
                source=f"service_runtime:{service_id}",
                payload=to_plain(payload),
            )
        except Exception:
            return
