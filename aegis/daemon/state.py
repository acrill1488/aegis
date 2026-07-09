"""Shared daemon process state and heartbeat files."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any


DEFAULT_DAEMON_DIR = Path("F:/AI_WORKSPACE/daemon")
DAEMON_STATE_FILE = "daemon.state.json"

STATE_STARTING = "STARTING"
STATE_READY = "READY"
STATE_DEAD = "DEAD"
STATE_STALE = "STALE"
STATE_STOPPING = "STOPPING"


class DaemonStateStore:
    def __init__(self, daemon_dir: Path = DEFAULT_DAEMON_DIR):
        self.daemon_dir = daemon_dir
        self.state_path = daemon_dir / DAEMON_STATE_FILE

    def write(
        self,
        state: str,
        *,
        pid: int | None = None,
        host: str | None = None,
        port: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.daemon_dir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        record = {
            "state": state,
            "pid": pid if pid is not None else os.getpid(),
            "host": host,
            "port": port,
            "updated_at": now,
            "heartbeat_at": now,
        }
        if details:
            record["details"] = details
        tmp_path = self.state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(record, ensure_ascii=True, indent=2), encoding="utf-8")
        tmp_path.replace(self.state_path)
        return record

    def read(self) -> dict[str, Any] | None:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None


class DaemonHeartbeat:
    def __init__(
        self,
        store: DaemonStateStore,
        *,
        state: str,
        pid: int,
        host: str,
        port: int,
        interval: float = 1.0,
    ):
        self.store = store
        self.state = state
        self.pid = pid
        self.host = host
        self.port = port
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.store.write(self.state, pid=self.pid, host=self.host, port=self.port)
        self._thread = threading.Thread(target=self._run, name="aegis-daemon-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            self.store.write(self.state, pid=self.pid, host=self.host, port=self.port)
