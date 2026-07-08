from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BaseWatcher(ABC):
    """Base contract for Scheduler-managed passive watchers."""

    def __init__(
        self,
        *,
        id: str,
        name: str,
        interval: int | float,
        scheduler: Any,
        event_bus: Any,
        live_context: Any,
        enabled: bool = True,
    ) -> None:
        if not id:
            raise ValueError("Watcher id must not be empty.")
        if not name:
            raise ValueError("Watcher name must not be empty.")
        if float(interval) <= 0:
            raise ValueError("Watcher interval must be greater than zero.")

        self.id = id
        self.name = name
        self.interval = float(interval)
        self.enabled = enabled
        self.scheduler = scheduler
        self.event_bus = event_bus
        self.live_context = live_context
        self._status = "created"
        self._health_state = "unknown"
        self._degraded_reason: str | None = None
        self._error_count = 0
        self._last_error: str | None = None
        self._last_successful_tick: str | None = None
        self._last_publication: dict | None = None

    def start(self) -> dict:
        self._status = "running"
        self._health_state = "healthy"
        return self.status()

    def stop(self) -> None:
        self._status = "stopped"

    @abstractmethod
    def tick(self) -> None:
        """Perform one bounded observation pass."""

    def publish(self, event_type: str, payload: dict) -> Any:
        receipt = self.event_bus.publish(
            event_type,
            source=getattr(self, "source", self.id),
            payload=payload,
        )
        self._last_publication = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
        }
        return receipt

    def update_context(
        self,
        key: str,
        value: dict,
        *,
        ttl_seconds: int | None = None,
        metadata: dict | None = None,
    ) -> Any:
        kwargs = {
            "key": key,
            "value": value,
            "source": getattr(self, "source", self.id),
        }
        if ttl_seconds is not None:
            kwargs["ttl_seconds"] = ttl_seconds
        if metadata is not None:
            kwargs["metadata"] = metadata
        return self.live_context.set(**kwargs)

    def health(self) -> dict:
        return {
            "state": self._health_state,
            "ready": self._status in {"running", "degraded"},
            "live": self._status not in {"failed", "stopped"},
            "degraded_reason": self._degraded_reason,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "last_successful_tick": self._last_successful_tick,
            "last_publication": self._last_publication,
        }

    def status(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "interval": self.interval,
            "enabled": self.enabled,
            "status": self._status,
            "health": self.health(),
        }

    def mark_tick_success(self) -> None:
        self._last_successful_tick = datetime.now().isoformat()
        self._last_error = None
        self._degraded_reason = None
        if self._status != "stopped":
            self._status = "running"
        self._health_state = "healthy"

    def mark_tick_error(self, error: Exception) -> None:
        self._error_count += 1
        self._last_error = str(error)
        self._degraded_reason = str(error)
        if self._status != "stopped":
            self._status = "degraded"
        self._health_state = "degraded"
