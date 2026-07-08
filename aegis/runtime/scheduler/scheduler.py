from __future__ import annotations

import logging
import threading
from time import monotonic
from typing import Callable

from aegis.watchers import BaseWatcher, WatcherRegistry

from .registry import TaskRegistry
from .task import ScheduledTask


_LOGGER = logging.getLogger(__name__)


class Scheduler:
    """Single-threaded periodic task scheduler."""

    def __init__(
        self,
        registry: TaskRegistry | None = None,
        *,
        watcher_registry: WatcherRegistry | None = None,
        tick_seconds: int | float = 0.5,
    ) -> None:
        self.task_registry = registry or TaskRegistry()
        self.watcher_registry = watcher_registry or WatcherRegistry()
        self.registry = _SchedulerRegistryFacade(
            self.task_registry,
            self.watcher_registry,
        )
        self.tick_seconds = float(tick_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._started = False
        self._watcher_tasks: dict[str, ScheduledTask] = {}

    def register_periodic(
        self,
        name: str,
        callback: Callable[[], None],
        interval_seconds: int | float,
        *,
        run_immediately: bool = False,
        replace: bool = False,
    ) -> ScheduledTask:
        return self.task_registry.register_periodic(
            name,
            callback,
            interval_seconds,
            run_immediately=run_immediately,
            replace=replace,
        )

    def unregister(self, name: str) -> ScheduledTask | None:
        return self.task_registry.unregister(name)

    def run_once(self, name: str) -> ScheduledTask:
        task = self.task_registry.get(name)
        if task is not None:
            self._run_task(task)
            return task

        watcher = self.watcher_registry.get(name)
        if watcher is None:
            raise KeyError(name)
        task = self._task_for_watcher(watcher, run_immediately=True)
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
        tasks = self.task_registry.status()
        watcher_tasks = [
            self._task_for_watcher(watcher).status()
            for watcher in self.watcher_registry.list()
        ]
        return {
            "scheduler": "runtime",
            "running": self._started and thread_alive,
            "thread_alive": thread_alive,
            "tick_seconds": self.tick_seconds,
            "task_count": len(tasks) + len(watcher_tasks),
            "tasks": tasks + watcher_tasks,
            "watchers": [
                BaseWatcher.status(watcher) for watcher in self.watcher_registry.list()
            ],
        }

    def _run(self) -> None:
        while not self._stop_event.is_set():
            now = monotonic()
            next_due_at: float | None = None

            for task in self.task_registry.list():
                if not task.enabled:
                    continue
                if task.next_run_at > now:
                    next_due_at = _earlier(next_due_at, task.next_run_at)
                    continue

                self._run_task(task)
                next_due_at = _earlier(next_due_at, task.next_run_at)

            for watcher in self.watcher_registry.enabled():
                task = self._task_for_watcher(watcher)
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

    def _task_for_watcher(
        self,
        watcher: BaseWatcher,
        *,
        run_immediately: bool = False,
    ) -> ScheduledTask:
        task = self._watcher_tasks.get(watcher.id)
        if (
            task is None
            or task.callback != watcher.tick
            or task.interval_seconds != watcher.interval
        ):
            task = ScheduledTask.periodic(
                watcher.id,
                watcher.tick,
                watcher.interval,
                run_immediately=run_immediately,
            )
            task.enabled = watcher.enabled
            self._watcher_tasks[watcher.id] = task
        return task

    def _run_task(self, task: ScheduledTask) -> None:
        watcher = self.watcher_registry.get(task.name)
        try:
            task.callback()
        except Exception as exc:  # pragma: no cover - defensive boundary
            task.mark_error(exc, monotonic())
            if watcher is not None:
                watcher.mark_tick_error(exc)
            _LOGGER.exception("Scheduled task failed: %s", task.name)
        else:
            task.mark_success(monotonic())
            if watcher is not None:
                watcher.mark_tick_success()


def _earlier(current: float | None, candidate: float) -> float:
    if current is None:
        return candidate
    return min(current, candidate)


class _SchedulerRegistryFacade:
    """Compatibility view over legacy tasks and watcher registry."""

    def __init__(
        self,
        task_registry: TaskRegistry,
        watcher_registry: WatcherRegistry,
    ) -> None:
        self._tasks = task_registry
        self._watchers = watcher_registry

    def register(self, task: ScheduledTask, *, replace: bool = False) -> ScheduledTask:
        return self._tasks.register(task, replace=replace)

    def register_periodic(
        self,
        name: str,
        callback: Callable[[], None],
        interval_seconds: int | float,
        *,
        run_immediately: bool = False,
        replace: bool = False,
    ) -> ScheduledTask:
        return self._tasks.register_periodic(
            name,
            callback,
            interval_seconds,
            run_immediately=run_immediately,
            replace=replace,
        )

    def unregister(self, name: str) -> ScheduledTask | BaseWatcher | None:
        task = self._tasks.unregister(name)
        if task is not None:
            return task
        return self._watchers.unregister(name)

    def get(self, name: str) -> ScheduledTask | BaseWatcher | None:
        task = self._tasks.get(name)
        if task is not None:
            return task
        return self._watchers.get(name)

    def list(self) -> list[ScheduledTask | BaseWatcher]:
        return [*self._tasks.list(), *self._watchers.list()]

    def status(self) -> list[dict]:
        return self._tasks.status()
