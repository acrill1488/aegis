from __future__ import annotations

from .base import BaseService


class ServiceRegistry:
    def __init__(self):
        self._services: dict[str, BaseService] = {}

    def register(self, service: BaseService) -> BaseService:
        self._services[service.id] = service
        return service

    def get(self, service_id: str) -> BaseService | None:
        return self._services.get(service_id)

    def list(self) -> list[BaseService]:
        return list(self._services.values())
