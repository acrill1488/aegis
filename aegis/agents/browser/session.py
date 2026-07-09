from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from aegis.capabilities import CapabilityInvocationRequest
from aegis.core.core import AegisCore
from aegis.serialization import to_plain


DEFAULT_SESSION_HOST = "127.0.0.1"
DEFAULT_SESSION_PORT = 8765
DEFAULT_SESSION_PATH = Path("F:/AI_WORKSPACE/browser/session.json")


class BrowserSessionUnavailable(RuntimeError):
    pass


class BrowserSessionServer:
    def __init__(
        self,
        *,
        host: str = DEFAULT_SESSION_HOST,
        port: int = DEFAULT_SESSION_PORT,
        session_path: Path | str = DEFAULT_SESSION_PATH,
        headless: bool = False,
    ):
        self.host = host
        self.port = port
        self.session_path = Path(session_path)
        self.headless = headless
        self.core = AegisCore()
        self._server: HTTPServer | None = None

    def serve_forever(self, on_ready: Callable[[], None] | None = None) -> None:
        handler = self._handler()
        self._server = HTTPServer((self.host, self.port), handler)
        try:
            self._start_browser()
            self._write_state()
            if on_ready is not None:
                on_ready()
            self._server.serve_forever()
        finally:
            self.close()

    def close(self) -> None:
        try:
            self.core.capability_runtime.invoke(
                CapabilityInvocationRequest(
                    capability_id="browser.close",
                    payload={},
                    caller="browser-session",
                )
            )
        finally:
            if self._server is not None:
                self._server.server_close()
            self._remove_state()

    def _start_browser(self) -> None:
        self.core.capability_runtime.invoke(
            CapabilityInvocationRequest(
                capability_id="browser.open",
                payload={"headless": self.headless},
                caller="browser-session",
            )
        )

    def _write_state(self) -> None:
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "pid": os.getpid(),
            "host": self.host,
            "port": self.port,
            "url": f"http://{self.host}:{self.port}",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self.session_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _remove_state(self) -> None:
        try:
            self.session_path.unlink()
        except FileNotFoundError:
            return

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != "/health":
                    self._send_json(404, {"success": False, "error": "Not found"})
                    return
                self._send_json(200, {"success": True, "status": "running"})

            def do_POST(self) -> None:
                if self.path != "/invoke":
                    self._send_json(404, {"success": False, "error": "Not found"})
                    return

                try:
                    request = self._read_json()
                    result = outer.core.capability_runtime.invoke(
                        CapabilityInvocationRequest(
                            capability_id=str(request.get("capability_id", "")),
                            payload=dict(request.get("payload", {}) or {}),
                            caller="browser-session-client",
                        )
                    )
                    self._send_json(
                        200,
                        {
                            "success": result.success,
                            "output": to_plain(result.output),
                            "error": result.error,
                            "metadata": to_plain(result.metadata),
                        },
                    )
                except Exception as exc:
                    self._send_json(500, {"success": False, "error": str(exc)})

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                return json.loads(raw.decode("utf-8"))

            def _send_json(self, status: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler


class BrowserSessionClient:
    def __init__(self, session_path: Path | str = DEFAULT_SESSION_PATH):
        self.session_path = Path(session_path)

    def is_running(self) -> bool:
        try:
            self._request("GET", "/health")
        except BrowserSessionUnavailable:
            return False
        return True

    def invoke(self, capability_id: str, payload: dict) -> dict:
        response = self._request(
            "POST",
            "/invoke",
            {"capability_id": capability_id, "payload": payload},
        )
        if not response.get("success"):
            raise RuntimeError(str(response.get("error") or "Browser invocation failed"))
        output = response.get("output")
        return output if isinstance(output, dict) else {"result": output}

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:
        state = self._read_state()
        base_url = state.get("url") or f"http://{state['host']}:{state['port']}"
        data = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        request = Request(
            f"{base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError, KeyError) as exc:
            raise BrowserSessionUnavailable(
                "Browser session is not running. Start it with: aegis browser serve"
            ) from exc

    def _read_state(self) -> dict:
        try:
            return json.loads(self.session_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise BrowserSessionUnavailable(
                "Browser session is not running. Start it with: aegis browser serve"
            ) from exc
