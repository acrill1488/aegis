from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

from .client import (
    DEFAULT_BROWSER_SERVICE_HOST,
    DEFAULT_BROWSER_SERVICE_PORT,
    DEFAULT_BROWSER_SERVICE_STATE_PATH,
)
from .service import BrowserService


class BrowserServiceServer:
    def __init__(
        self,
        *,
        host: str = DEFAULT_BROWSER_SERVICE_HOST,
        port: int = DEFAULT_BROWSER_SERVICE_PORT,
        state_path: Path | str = DEFAULT_BROWSER_SERVICE_STATE_PATH,
        headless: bool = False,
    ):
        self.host = host
        self.port = port
        self.state_path = Path(state_path)
        self.core = AegisCore()
        self.service = BrowserService(headless=headless)
        self._server: HTTPServer | None = None

    def serve_forever(self, on_ready: Callable[[], None] | None = None) -> None:
        self.core.service_runtime.register(self.service)
        self._server = HTTPServer((self.host, self.port), self._handler())
        try:
            self.core.service_runtime.start(self.service.id)
            self._write_state()
            if on_ready is not None:
                on_ready()
            self._server.serve_forever()
        finally:
            self.close()

    def close(self) -> None:
        try:
            if self.service.status.value not in {"stopped", "stopping"}:
                self.core.service_runtime.stop(self.service.id)
        finally:
            if self._server is not None:
                self._server.server_close()
            self._remove_state()

    def _write_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "pid": os.getpid(),
            "host": self.host,
            "port": self.port,
            "url": f"http://{self.host}:{self.port}",
            "service_id": self.service.id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _remove_state(self) -> None:
        try:
            self.state_path.unlink()
        except FileNotFoundError:
            return

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != "/health":
                    self._send_json(404, {"success": False, "error": "Not found"})
                    return
                self._send_json(200, {"success": True, "health": outer.service.health()})

            def do_POST(self) -> None:
                if self.path != "/invoke":
                    self._send_json(404, {"success": False, "error": "Not found"})
                    return
                try:
                    request = self._read_json()
                    output = outer.service.invoke(
                        str(request.get("action", "")),
                        dict(request.get("payload", {}) or {}),
                    )
                    self._send_json(200, {"success": True, "output": to_plain(output)})
                except Exception as exc:
                    self._send_json(500, {"success": False, "error": str(exc)})

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                return json.loads(raw.decode("utf-8"))

            def _send_json(self, status: int, payload: dict) -> None:
                body = json.dumps(to_plain(payload)).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler
