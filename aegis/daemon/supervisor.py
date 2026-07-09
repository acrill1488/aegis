"""Background process supervisor for the local AEGIS daemon."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from aegis.daemon.state import (
    DEFAULT_DAEMON_DIR,
    DaemonStateStore,
    STATE_DEAD,
    STATE_READY,
    STATE_STALE,
    STATE_STARTING,
    STATE_STOPPING,
)
from aegis.ipc import IPCClient, IPCConnectionError


DEFAULT_DAEMON_LOG_PATH = DEFAULT_DAEMON_DIR / "daemon.log"
DEFAULT_DAEMON_PID_PATH = DEFAULT_DAEMON_DIR / "daemon.pid"
DEFAULT_IPC_HOST = "127.0.0.1"
DEFAULT_IPC_PORT = 8787
HEARTBEAT_STALE_AFTER_SECONDS = 5.0


class DaemonSupervisor:
    """Start, inspect, and stop the local daemon without owning daemon runtime logic."""

    def __init__(
        self,
        *,
        host: str = DEFAULT_IPC_HOST,
        port: int = DEFAULT_IPC_PORT,
        daemon_dir: Path = DEFAULT_DAEMON_DIR,
        python_executable: str | None = None,
        cwd: Path | None = None,
        startup_timeout: float = 10.0,
    ):
        self.host = host
        self.port = port
        self.daemon_dir = daemon_dir
        self.log_path = daemon_dir / "daemon.log"
        self.pid_path = daemon_dir / "daemon.pid"
        self.state_store = DaemonStateStore(daemon_dir)
        self.python_executable = python_executable or sys.executable
        self.cwd = cwd or Path(__file__).resolve().parents[2]
        self.startup_timeout = startup_timeout

    def is_running(self) -> bool:
        status = self.status()
        return bool(status and status.get("state") == STATE_READY)

    def status(self) -> dict[str, Any] | None:
        ipc_status = self._ipc_status()
        pid = self._read_pid()
        daemon_state = self.state_store.read()
        if ipc_status is not None:
            stale_pid = None
            if pid is not None and (
                not self._pid_exists(pid) or not self._process_matches_daemon(pid)
            ):
                stale_pid = pid
                self._remove_pid_file()
                pid = None
            return self._status_payload(
                STATE_READY,
                running=True,
                pid=pid,
                stale_pid=stale_pid,
                ipc=ipc_status,
                heartbeat=daemon_state,
            )
        if pid is None:
            return self._status_payload(STATE_DEAD, running=False, heartbeat=daemon_state)
        if not self._pid_exists(pid):
            self._remove_pid_file()
            return self._status_payload(
                STATE_STALE,
                running=False,
                stale_pid=pid,
                heartbeat=daemon_state,
                message="Removed stale daemon pid file.",
            )
        if not self._process_matches_daemon(pid):
            self._remove_pid_file()
            return self._status_payload(
                STATE_STALE,
                running=False,
                stale_pid=pid,
                heartbeat=daemon_state,
                message="Removed pid file for a non-daemon process.",
            )
        state = self._state_from_heartbeat(daemon_state)
        return self._status_payload(state, running=False, pid=pid, heartbeat=daemon_state)

    def start_background(self) -> dict[str, Any]:
        current_status = self.status()
        if current_status and current_status.get("state") == STATE_READY:
            return {"running": True, "started": False, "status": current_status}

        self.daemon_dir.mkdir(parents=True, exist_ok=True)
        command = self._command()
        popen_kwargs: dict[str, Any] = {
            "cwd": str(self.cwd),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = self._creation_flags()
        with self.log_path.open("ab") as log_file:
            popen_kwargs["stdout"] = log_file
            process = subprocess.Popen(
                command,
                **popen_kwargs,
            )
        self._write_pid(process.pid)

        status = self._wait_until_ready(process)
        if status is None:
            current = self.status()
            return {
                "running": False,
                "started": True,
                "pid": process.pid,
                "state": current.get("state") if current else STATE_DEAD,
                "status": current,
                "error": "AEGIS daemon did not reach READY state.",
                "log_file": str(self.log_path),
                "pid_file": str(self.pid_path),
            }
        return {
            "state": STATE_READY,
            "running": True,
            "started": True,
            "pid": process.pid,
            "status": status,
            "log_file": str(self.log_path),
            "pid_file": str(self.pid_path),
        }

    def ensure_running(self) -> dict[str, Any]:
        current_status = self.status()
        if current_status and current_status.get("state") == STATE_READY:
            return {"running": True, "started": False, "status": current_status}
        return self.start_background()

    def stop(self) -> dict[str, Any]:
        pid = self._read_pid()
        if pid is None:
            return {
                "state": STATE_DEAD,
                "running": False,
                "stopped": False,
                "message": "AEGIS daemon is not running and no pid file was found.",
                "log_file": str(self.log_path),
                "pid_file": str(self.pid_path),
            }

        if not self._pid_exists(pid):
            self._remove_pid_file()
            return {
                "state": STATE_STALE,
                "running": False,
                "stopped": False,
                "stale_pid": pid,
                "message": "Removed stale daemon pid file.",
                "log_file": str(self.log_path),
                "pid_file": str(self.pid_path),
            }

        if not self._process_matches_daemon(pid):
            self._remove_pid_file()
            return {
                "state": STATE_STALE,
                "running": False,
                "stopped": False,
                "stale_pid": pid,
                "error": "Pid file points to a process that does not look like AEGIS daemon.",
                "log_file": str(self.log_path),
                "pid_file": str(self.pid_path),
            }

        self.state_store.write(STATE_STOPPING, pid=pid, host=self.host, port=self.port)
        self._terminate_process(pid)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not self._pid_exists(pid):
                self._remove_pid_file()
                return {
                    "state": STATE_DEAD,
                    "running": False,
                    "stopped": True,
                    "pid": pid,
                    "log_file": str(self.log_path),
                    "pid_file": str(self.pid_path),
                }
            time.sleep(0.2)

        self._kill_process(pid)
        self._remove_pid_file()
        return {
            "state": STATE_DEAD,
            "running": False,
            "stopped": True,
            "pid": pid,
            "forced": True,
            "log_file": str(self.log_path),
            "pid_file": str(self.pid_path),
        }

    def _command(self) -> list[str]:
        return [
            self.python_executable,
            "-m",
            "aegis.cli.main",
            "daemon",
            "serve",
            "--host",
            self.host,
            "--port",
            str(self.port),
        ]

    def _creation_flags(self) -> int:
        if os.name != "nt":
            return 0
        return (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    def _wait_until_ready(self, process: subprocess.Popen[Any]) -> dict[str, Any] | None:
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                return None
            status = self.status()
            if status and status.get("state") == STATE_READY:
                return status
            time.sleep(0.25)
        return None

    def _state_from_heartbeat(self, daemon_state: dict[str, Any] | None) -> str:
        if not daemon_state:
            return STATE_STARTING
        state = str(daemon_state.get("state") or "").upper()
        if state == STATE_STOPPING:
            return STATE_STOPPING
        heartbeat_at = daemon_state.get("heartbeat_at")
        if isinstance(heartbeat_at, (int, float)):
            if time.time() - float(heartbeat_at) > HEARTBEAT_STALE_AFTER_SECONDS:
                return STATE_DEAD
        if state in {STATE_STARTING, STATE_READY}:
            return STATE_STARTING
        return STATE_DEAD

    def _status_payload(self, state: str, *, running: bool, **extra: Any) -> dict[str, Any]:
        payload = {
            "state": state,
            "running": running,
            "log_file": str(self.log_path),
            "pid_file": str(self.pid_path),
            "state_file": str(self.state_store.state_path),
        }
        payload.update({key: value for key, value in extra.items() if value is not None})
        return payload

    def _ipc_status(self) -> dict[str, Any] | None:
        try:
            output = IPCClient(host=self.host, port=self.port, timeout=1.0).request(
                "health",
                "status",
            )
        except (IPCConnectionError, RuntimeError, OSError):
            return None
        if isinstance(output, dict) and output.get("status") == "ok":
            return output
        return None

    def _read_pid(self) -> int | None:
        try:
            value = self.pid_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _write_pid(self, pid: int) -> None:
        self.pid_path.write_text(str(pid), encoding="utf-8")

    def _remove_pid_file(self) -> None:
        try:
            self.pid_path.unlink()
        except FileNotFoundError:
            return

    def _pid_exists(self, pid: int) -> bool:
        try:
            import psutil
        except ImportError:
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ValueError):
                return False
        return psutil.pid_exists(pid)

    def _process_matches_daemon(self, pid: int) -> bool:
        try:
            import psutil
        except ImportError:
            return True
        try:
            process = psutil.Process(pid)
            command_line = " ".join(process.cmdline()).casefold()
        except psutil.AccessDenied:
            return True
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return False
        return "aegis" in command_line and "daemon" in command_line and "serve" in command_line

    def _terminate_process(self, pid: int) -> None:
        if os.name == "nt":
            self._terminate_windows(pid)
            return
        os.kill(pid, signal.SIGTERM)

    def _kill_process(self, pid: int) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
        os.kill(pid, signal.SIGKILL)

    def _terminate_windows(self, pid: int) -> None:
        try:
            import psutil
        except ImportError:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return
        for child in process.children(recursive=True):
            child.terminate()
        process.terminate()
