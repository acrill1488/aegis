from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Callable


TaskCallback = Callable[[], None]


@dataclass
class ScheduledTask:
    """Periodic task definition and runtime state."""

    name: str
    callback: TaskCallback
    interval_seconds: float
    next_run_at: float = field(default_factory=monotonic)
    last_run_at: float | None = None
    run_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Scheduled task name must not be empty.")
        if self.interval_seconds <= 0:
            raise ValueError("Scheduled task interval must be greater than zero.")

    @classmethod
    def periodic(
        cls,
        name: str,
        callback: TaskCallback,
        interval_seconds: int | float,
        *,
        run_immediately: bool = False,
    ) -> "ScheduledTask":
        interval = float(interval_seconds)
        now = monotonic()
        next_run_at = now if run_immediately else now + interval
        return cls(
            name=name,
            callback=callback,
            interval_seconds=interval,
            next_run_at=next_run_at,
        )

    def mark_success(self, finished_at: float) -> None:
        self.last_run_at = finished_at
        self.run_count += 1
        self.last_error = None
        self.next_run_at = finished_at + self.interval_seconds

    def mark_error(self, error: Exception, finished_at: float) -> None:
        self.last_run_at = finished_at
        self.run_count += 1
        self.error_count += 1
        self.last_error = str(error)
        self.next_run_at = finished_at + self.interval_seconds

    def status(self, now: float | None = None) -> dict:
        current_time = monotonic() if now is None else now
        return {
            "name": self.name,
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "last_run_at": self.last_run_at,
            "next_run_in_seconds": max(self.next_run_at - current_time, 0.0),
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }
