from datetime import datetime
from typing import Callable

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only in incomplete environments.
    psutil = None

try:
    import win32gui
    import win32process
except ImportError:  # pragma: no cover - ctypes fallback covers this path.
    win32gui = None
    win32process = None


WindowEventCallback = Callable[[str, dict], None]
WINDOW_WATCHER_TASK_NAME = "window-watcher"


class WindowWatcher:
    """Watch the active Windows foreground window and mirror it into Live Context."""

    source = "window_watcher"

    def __init__(
        self,
        core,
        interval_seconds: int | float = 0.5,
        on_event: WindowEventCallback | None = None,
    ):
        self.core = core
        self.interval_seconds = interval_seconds
        self.on_event = on_event
        self._task_name = WINDOW_WATCHER_TASK_NAME
        self._running = False
        self._previous: dict | None = None
        self._last_window: dict | None = None
        self._last_event: dict | None = None
        self._error: str | None = None

    def start(self) -> dict:
        _require_windows_api()
        if self._running:
            return self.status()

        self.tick()
        self.core.scheduler.register_periodic(
            self._task_name,
            self.tick,
            self.interval_seconds,
            replace=True,
        )
        self._running = True
        self._error = None
        return self.status()

    def stop(self) -> None:
        self.core.scheduler.unregister(self._task_name)
        self._running = False

    def status(self) -> dict:
        scheduler_status = self.core.scheduler.status()
        task = self.core.scheduler.registry.get(self._task_name)
        thread_alive = bool(scheduler_status["thread_alive"] and task is not None)
        return {
            "watcher": "window",
            "running": self._running,
            "thread_alive": thread_alive,
            "interval_seconds": self.interval_seconds,
            "last_window": self._last_window,
            "last_event": self._last_event,
            "error": self._error,
            "scheduler_task": self._task_name if task is not None else None,
        }

    def tick(self) -> None:
        """Run one active-window check iteration."""
        try:
            window = self.snapshot()
            self._set_context(window)
            self._publish_focus_events(window)
            self._previous = window
            self._last_window = window
            self._error = None
        except Exception as exc:
            self._error = str(exc)
            raise

    def snapshot(self) -> dict:
        """Return the currently focused window."""
        _require_windows_api()
        hwnd = _foreground_hwnd()
        pid = _window_pid(hwnd)
        process_name = _process_name(pid)
        return {
            "hwnd": int(hwnd or 0),
            "pid": int(pid or 0),
            "process_name": process_name,
            "title": _window_title(hwnd),
            "timestamp": datetime.now().isoformat(),
        }

    def _set_context(self, window: dict) -> None:
        ttl_seconds = max(int(float(self.interval_seconds) * 3), 2)
        self.core.live_context.set(
            key="windows.active_window",
            value=window,
            source=self.source,
            ttl_seconds=ttl_seconds,
        )
        self.core.live_context.set(
            key="windows.active_process",
            value={"name": window.get("process_name") or ""},
            source=self.source,
            ttl_seconds=ttl_seconds,
        )
        self.core.live_context.set(
            key="windows.active_pid",
            value={"pid": int(window.get("pid") or 0)},
            source=self.source,
            ttl_seconds=ttl_seconds,
        )

    def _publish_focus_events(self, window: dict) -> None:
        if not _window_identity_changed(self._previous, window):
            return

        if self._previous is not None:
            self._publish_event("window.changed", window)
        self._publish_event("window.focused", window)

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
            key="windows.last_window_event",
            value=event_payload,
            source=self.source,
            ttl_seconds=3600,
        )
        self._last_event = event_payload

        if self.on_event is not None:
            self.on_event(event_type, event_payload)


def _window_identity_changed(previous: dict | None, current: dict) -> bool:
    if previous is None:
        return True
    return any(
        previous.get(key) != current.get(key)
        for key in ("hwnd", "pid", "process_name", "title")
    )


def _foreground_hwnd() -> int:
    if win32gui is not None:
        return int(win32gui.GetForegroundWindow())

    import ctypes

    return int(ctypes.windll.user32.GetForegroundWindow())


def _window_pid(hwnd: int) -> int:
    if not hwnd:
        return 0
    if win32process is not None:
        _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
        return int(pid or 0)

    import ctypes

    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(int(hwnd), ctypes.byref(pid))
    return int(pid.value or 0)


def _window_title(hwnd: int) -> str:
    if not hwnd:
        return ""
    if win32gui is not None:
        return win32gui.GetWindowText(hwnd) or ""

    import ctypes

    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(int(hwnd))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(int(hwnd), buffer, length + 1)
    return buffer.value


def _process_name(pid: int) -> str:
    if not pid or psutil is None:
        return ""
    try:
        return psutil.Process(int(pid)).name() or ""
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def _require_windows_api() -> None:
    if win32gui is not None and win32process is not None:
        return

    try:
        import ctypes

        ctypes.windll.user32.GetForegroundWindow
    except (AttributeError, OSError) as exc:
        raise RuntimeError(
            "WindowWatcher requires Windows foreground-window APIs. "
            "Install pywin32 or run on Windows with ctypes support."
        ) from exc
