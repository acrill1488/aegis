from __future__ import annotations

from enum import StrEnum


class ServiceStatus(StrEnum):
    created = "created"
    starting = "starting"
    running = "running"
    degraded = "degraded"
    stopping = "stopping"
    stopped = "stopped"
    failed = "failed"
