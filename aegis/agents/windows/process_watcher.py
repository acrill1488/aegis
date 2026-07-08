import threading
from datetime import datetime
from typing import Callable

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only in incomplete environments.
    psutil = None


ProcessEventCallback = Callable[[str, dict], None]


class ProcessWatcher:
    """Watch process start/stop events and mirror them into Live Context."""

    source = "process_watcher"

    def __init__(
        self,
        core,
        interval_seconds: int | float = 5,
        on_event: ProcessEventCallback | None = None,
    ):
        self.core = core
        self.interval_seconds = interval_seconds
        self.on_event = on_event
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._previous: dict[tuple[int, str], dict] = {}
        self._running = False
        self._last_event: dict | None = None
        self._error: str | None = None

    def start(self) -> dict:
        _require_psutil()
        if self._running:
            return self.status()

        self._previous = self._snapshot()
        self._set_running_context(self._previous)
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="aegis-process-watcher",
            daemon=True,
        )
        self._thread.start()
        self._running = True
        self._error = None
        return self.status()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(float(self.interval_seconds), 1.0) + 1.0)
            self._thread = None
        self._running = False

    def status(self) -> dict:
        thread_alive = bool(self._thread is not None and self._thread.is_alive())
        return {
            "watcher": "process",
            "running": self._running,
            "thread_alive": thread_alive,
            "interval_seconds": self.interval_seconds,
            "process_count": len(self._previous),
            "last_event": self._last_event,
            "error": self._error,
        }

    def _run(self) -> None:
        while not self._stop_event.wait(float(self.interval_seconds)):
            try:
                current = self._snapshot()
                self._publish_changes(current)
                self._set_running_context(current)
                self._previous = current
                self._error = None
            except Exception as exc:  # pragma: no cover - defensive boundary
                self._error = str(exc)

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

        self.core.events.publish(
            event_type,
            source=self.source,
            payload=event_payload,
        )
        self.core.live_context.set(
            key="processes.last_event",
            value=event_payload,
            source=self.source,
            ttl_seconds=3600,
        )
        self._last_event = event_payload

        if self.on_event is not None:
            self.on_event(event_type, event_payload)

    def _set_running_context(self, processes: dict[tuple[int, str], dict]) -> None:
        self.core.live_context.set(
            key="processes.running",
            value={
                "count": len(processes),
                "processes": list(processes.values()),
            },
            source=self.source,
            ttl_seconds=60,
        )


def _require_psutil() -> None:
    if psutil is None:
        raise RuntimeError(
            "ProcessWatcher requires psutil. Install dependencies with "
            "`pip install -r requirements/base.txt`."
        )
