from datetime import datetime
from typing import Callable

from aegis.watchers import BaseWatcher

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only in incomplete environments.
    psutil = None


ProcessEventCallback = Callable[[str, dict], None]
PROCESS_WATCHER_TASK_NAME = "process-watcher"


class ProcessWatcher(BaseWatcher):
    """Watch process start/stop events and mirror them into Live Context."""

    source = "process_watcher"

    def __init__(
        self,
        core,
        interval_seconds: int | float = 5,
        on_event: ProcessEventCallback | None = None,
    ):
        super().__init__(
            id=PROCESS_WATCHER_TASK_NAME,
            name="Process Watcher",
            interval=interval_seconds,
            scheduler=core.scheduler,
            event_bus=core.events,
            live_context=core.live_context,
        )
        self.interval_seconds = interval_seconds
        self.on_event = on_event
        self._task_name = PROCESS_WATCHER_TASK_NAME
        self._previous: dict[tuple[int, str], dict] = {}
        self._running = False
        self._last_event: dict | None = None
        self._error: str | None = None

    def start(self) -> dict:
        _require_psutil()
        if self._running:
            return self.status()

        self._previous = self._snapshot()
        self.scheduler.watcher_registry.register(self, replace=True)
        self._running = True
        self._error = None
        super().start()
        return self.status()

    def stop(self) -> None:
        self.scheduler.watcher_registry.unregister(self.id)
        self._running = False
        super().stop()

    def status(self) -> dict:
        scheduler_status = self.scheduler.status()
        task = self.scheduler.registry.get(self._task_name)
        thread_alive = bool(scheduler_status["thread_alive"] and task is not None)
        return {
            "watcher": "process",
            "running": self._running,
            "thread_alive": thread_alive,
            "interval_seconds": self.interval_seconds,
            "process_count": len(self._previous),
            "last_event": self._last_event,
            "error": self._error,
            "scheduler_task": self._task_name if task is not None else None,
        }

    def tick(self) -> None:
        """Run one process check iteration."""
        try:
            current = self._snapshot()
            self._publish_changes(current)
            self._set_running_context(current)
            self._previous = current
            self._error = None
            self.mark_tick_success()
        except Exception as exc:
            self._error = str(exc)
            self.mark_tick_error(exc)
            raise

    def _snapshot(self) -> dict[tuple[int, str], dict]:
        _require_psutil()
        processes: dict[tuple[int, str], dict] = {}
        for process in psutil.process_iter(attrs=["pid", "name", "username"]):
            try:
                info = process.info
                name = info.get("name") or ""
                pid = int(info["pid"])
                processes[(pid, name)] = {
                    "pid": pid,
                    "name": name,
                    "username": info.get("username"),
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return processes

    def _publish_changes(self, current: dict[tuple[int, str], dict]) -> None:
        previous_keys = set(self._previous)
        current_keys = set(current)

        for key in sorted(current_keys - previous_keys):
            self._publish_event("process.started", current[key])
        for key in sorted(previous_keys - current_keys):
            self._publish_event("process.stopped", self._previous[key])

    def _publish_event(self, event_type: str, payload: dict) -> None:
        event_payload = dict(payload)
        event_payload["event"] = event_type
        event_payload["timestamp"] = datetime.now().isoformat()

        self.publish(event_type, event_payload)
        self.update_context(
            key="processes.last_event",
            value=event_payload,
            ttl_seconds=3600,
        )
        self._last_event = event_payload

        if self.on_event is not None:
            self.on_event(event_type, event_payload)

    def _set_running_context(self, processes: dict[tuple[int, str], dict]) -> None:
        self.update_context(
            key="processes.running",
            value={
                "count": len(processes),
                "processes": list(processes.values()),
            },
            ttl_seconds=60,
        )


def _require_psutil() -> None:
    if psutil is None:
        raise RuntimeError(
            "ProcessWatcher requires psutil. Install dependencies with "
            "`pip install -r requirements/base.txt`."
        )
