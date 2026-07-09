from __future__ import annotations

from .models import ServiceStatus


class BaseService:
    id: str
    name: str

    def __init__(self, service_id: str, name: str):
        self.id = service_id
        self.name = name
        self.status = ServiceStatus.created

    def start(self) -> dict:
        self.status = ServiceStatus.running
        return self.status_dict()

    def stop(self) -> dict:
        self.status = ServiceStatus.stopped
        return self.status_dict()

    def health(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "healthy": self.status == ServiceStatus.running,
        }

    def status_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
        }
