from __future__ import annotations

import platform
import shlex
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import DesktopApp, DesktopWindow

try:
    import psutil
except ImportError:  # pragma: no cover - dependency is optional at import time.
    psutil = None

try:
    import win32con
    import win32gui
    import win32process
except ImportError:  # pragma: no cover - ctypes fallback covers core paths.
    win32con = None
    win32gui = None
    win32process = None


class WindowsProvider:
    """Provider for local Windows desktop state and basic window control."""

    def list_windows(self) -> list[DesktopWindow]:
        self._require_windows()
        active_id = str(_foreground_hwnd() or "")
        windows: list[DesktopWindow] = []

        def collect(hwnd: int) -> None:
            title = _window_title(hwnd)
            visible = _is_window_visible(hwnd)
            if not title and not visible:
                return
            pid = _window_pid(hwnd)
            windows.append(
                DesktopWindow(
                    id=str(int(hwnd)),
                    title=title,
                    process_name=_process_name(pid),
                    pid=int(pid or 0),
                    active=str(int(hwnd)) == active_id,
                    visible=visible,
                    bounds=_window_bounds(hwnd),
                    metadata={"hwnd": int(hwnd), "provider": "windows"},
                )
            )

        _enum_windows(collect)
        return windows

    def active_window(self) -> DesktopWindow | None:
        self._require_windows()
        hwnd = _foreground_hwnd()
        if not hwnd:
            return None
        pid = _window_pid(hwnd)
        return DesktopWindow(
            id=str(int(hwnd)),
            title=_window_title(hwnd),
            process_name=_process_name(pid),
            pid=int(pid or 0),
            active=True,
            visible=_is_window_visible(hwnd),
            bounds=_window_bounds(hwnd),
            metadata={"hwnd": int(hwnd), "provider": "windows"},
        )

    def activate_window(self, window_id: str | int) -> DesktopWindow | None:
        self._require_windows()
        hwnd = _parse_hwnd(window_id)
        if not _window_exists(hwnd):
            raise ValueError(f"Window not found: {window_id}")
        _activate_window(hwnd)
        return self.active_window()

    def close_window(self, window_id: str | int) -> dict[str, Any]:
        self._require_windows()
        hwnd = _parse_hwnd(window_id)
        if not _window_exists(hwnd):
            raise ValueError(f"Window not found: {window_id}")
        _close_window(hwnd)
        return {"window_id": str(hwnd), "status": "close_requested"}

    def launch_app(self, command: str | list[str]) -> DesktopApp:
        if isinstance(command, str):
            command_args = shlex.split(command, posix=False)
        else:
            command_args = [str(part) for part in command]
        if not command_args:
            raise ValueError("launch_app requires a non-empty command")

        process = subprocess.Popen(command_args)  # noqa: S603 - intentional local app launch.
        executable = command_args[0]
        return DesktopApp(
            name=Path(executable).name,
            executable=executable,
            pid=int(process.pid),
            status="running",
            metadata={"command": command_args, "provider": "windows"},
        )

    def list_processes(self, limit: int = 100) -> list[DesktopApp]:
        _require_psutil()
        apps: list[DesktopApp] = []
        for process in psutil.process_iter(attrs=["pid", "name", "exe", "status", "username"]):
            if len(apps) >= int(limit):
                break
            try:
                info = process.info
                apps.append(
                    DesktopApp(
                        name=info.get("name") or "",
                        executable=info.get("exe") or "",
                        pid=int(info.get("pid") or 0),
                        status=info.get("status") or "unknown",
                        metadata={"username": info.get("username"), "provider": "windows"},
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return apps

    def screenshot(self, path: str | Path | None = None) -> dict[str, Any]:
        try:
            import mss
        except ImportError as exc:  # pragma: no cover - exercised only in incomplete envs.
            raise RuntimeError("Desktop screenshots require mss.") from exc

        target = Path(path) if path is not None else _default_screenshot_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with mss.mss() as capture:
            monitor = capture.monitors[0]
            image = capture.grab(monitor)
            mss.tools.to_png(image.rgb, image.size, output=str(target))
            return {
                "path": str(target),
                "width": int(image.width),
                "height": int(image.height),
                "monitor": dict(monitor),
                "created_at": datetime.now().isoformat(),
            }

    def _require_windows(self) -> None:
        if platform.system().lower() != "windows":
            raise RuntimeError("WindowsProvider is only available on Windows.")
        _require_windows_api()


def _enum_windows(callback) -> None:
    if win32gui is not None:
        win32gui.EnumWindows(lambda hwnd, _: (callback(int(hwnd)), True)[1], None)
        return

    import ctypes
    from ctypes import wintypes

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def wrapped(hwnd, _lparam):
        callback(int(hwnd))
        return True

    ctypes.windll.user32.EnumWindows(enum_proc(wrapped), 0)


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


def _is_window_visible(hwnd: int) -> bool:
    if win32gui is not None:
        return bool(win32gui.IsWindowVisible(hwnd))

    import ctypes

    return bool(ctypes.windll.user32.IsWindowVisible(int(hwnd)))


def _window_bounds(hwnd: int) -> dict[str, int]:
    if not hwnd:
        return {}
    if win32gui is not None:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    else:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(int(hwnd), ctypes.byref(rect))
        left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    return {
        "x": int(left),
        "y": int(top),
        "width": int(right - left),
        "height": int(bottom - top),
    }


def _window_exists(hwnd: int) -> bool:
    if win32gui is not None:
        return bool(win32gui.IsWindow(hwnd))

    import ctypes

    return bool(ctypes.windll.user32.IsWindow(int(hwnd)))


def _activate_window(hwnd: int) -> None:
    if win32gui is not None:
        if win32con is not None:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return

    import ctypes

    ctypes.windll.user32.ShowWindow(int(hwnd), 9)
    ctypes.windll.user32.SetForegroundWindow(int(hwnd))


def _close_window(hwnd: int) -> None:
    if win32gui is not None and win32con is not None:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return

    import ctypes

    ctypes.windll.user32.PostMessageW(int(hwnd), 0x0010, 0, 0)


def _process_name(pid: int) -> str:
    if not pid or psutil is None:
        return ""
    try:
        return psutil.Process(int(pid)).name() or ""
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def _parse_hwnd(window_id: str | int) -> int:
    try:
        return int(str(window_id), 0)
    except ValueError as exc:
        raise ValueError(f"Invalid window id: {window_id}") from exc


def _default_screenshot_path() -> Path:
    filename = f"aegis-desktop-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
    return Path(tempfile.gettempdir()) / filename


def _require_psutil() -> None:
    if psutil is None:
        raise RuntimeError("Desktop process listing requires psutil.")


def _require_windows_api() -> None:
    if win32gui is not None and win32process is not None:
        return
    try:
        import ctypes

        ctypes.windll.user32.GetForegroundWindow
    except (AttributeError, OSError) as exc:
        raise RuntimeError(
            "Windows desktop control requires Win32 APIs. Install pywin32 or run on Windows."
        ) from exc
