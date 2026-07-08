from __future__ import annotations

import logging
import threading
from time import monotonic
from typing import Callable

from .registry import TaskRegistry
from .task import ScheduledTask


_LOGGER = logging.getLogger(__name__)


class Scheduler:
    """Single-threaded periodic task scheduler."""

    def __init__(
        self,
        registry: TaskRegistry | None = None,
        *,
        tick_seconds: int | float = 0.5,
    ) -> None:
        self.registry = registry or TaskRegistry()
        self.tick_seconds = float(tick_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._started = False

    def register_periodic(
        self,
        name: str,
        callback: Callable[[], None],
        interval_seconds: int | float,
        *,
        run_immediately: bool = False,
        replace: bool = False,
    ) -> ScheduledTask:
        return self.registry.register_periodic(
            name,
            callback,
            interval_seconds,
            run_immediately=run_immediately,
            replace=replace,
        )

    def unregister(self, name: str) -> ScheduledTask | None:
        return self.registry.unregister(name)

    def run_once(self, name: str) -> ScheduledTask:
        task = self.registry.get(name)
        if task is None:
            raise KeyError(name)
        self._run_task(task)
        return task

    def start(self) -> dict:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                self._started = True
                return self.status()

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="aegis-scheduler",
                daemon=True,
            )
            self._thread.start()
            self._started = True
            return self.status()

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            self._stop_event.set()

        if thread is not None:
            thread.join(timeout=max(self.tick_seconds, 1.0) + 1.0)

        with self._lock:
            if self._thread is thread:
                self._thread = None
            self._started = False

    def status(self) -> dict:
        thread_alive = bool(self._thread is not None and self._thread.is_alive())
        tasks = self.registry.status()
        return {
            "scheduler": "runtime",
            "running": self._started and thread_alive,
            "thread_alive": thread_alive,
            "tick_seconds": self.tick_seconds,
            "task_count": len(tasks),
            "tasks": tasks,
        }

    def _run(self) -> None:
        while not self._stop_event.is_set():
            now = monotonic()
            next_due_at: float | None = None

            for task in self.registry.list():
                if not task.enabled:
                    continue
                if task.next_run_at > now:
                    next_due_at = _earlier(next_due_at, task.next_run_at)
                    continue

                self._run_task(task)
                next_due_at = _earlier(next_due_at, task.next_run_at)

            wait_seconds = self.tick_seconds
            if next_due_at is not None:
                wait_seconds = min(wait_seconds, max(next_due_at - monotonic(), 0.0))
            self._stop_event.wait(wait_seconds)

    def _run_task(self, task: ScheduledTask) -> None:
        try:
            task.callback()
        except Exception as exc:  # pragma: no cover - defensive boundary
            task.mark_error(exc, monotonic())
            _LOGGER.exception("Scheduled task failed: %s", task.name)
        else:
            task.mark_success(monotonic())


def _earlier(current: float | None, candidate: float) -> float:
    if current is None:
        return candidate
    return min(current, candidate)
