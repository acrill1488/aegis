from __future__ import annotations

from threading import RLock

from .task import ScheduledTask, TaskCallback


class TaskRegistry:
    """Thread-safe registry for named scheduled tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._lock = RLock()

    def register(self, task: ScheduledTask, *, replace: bool = False) -> ScheduledTask:
        with self._lock:
            if task.name in self._tasks and not replace:
                raise ValueError(f"Scheduled task already registered: {task.name}")
            self._tasks[task.name] = task
            return task

    def register_periodic(
        self,
        name: str,
        callback: TaskCallback,
        interval_seconds: int | float,
        *,
        run_immediately: bool = False,
        replace: bool = False,
    ) -> ScheduledTask:
        task = ScheduledTask.periodic(
            name,
            callback,
            interval_seconds,
            run_immediately=run_immediately,
        )
        return self.register(task, replace=replace)

    def unregister(self, name: str) -> ScheduledTask | None:
        with self._lock:
            return self._tasks.pop(name, None)

    def get(self, name: str) -> ScheduledTask | None:
        with self._lock:
            return self._tasks.get(name)

    def list(self) -> list[ScheduledTask]:
        with self._lock:
            return list(self._tasks.values())

    def status(self) -> list[dict]:
        with self._lock:
            return [task.status() for task in self._tasks.values()]
