from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_BROWSER_SERVICE_HOST = "127.0.0.1"
DEFAULT_BROWSER_SERVICE_PORT = 8765
DEFAULT_BROWSER_SERVICE_STATE_PATH = Path("F:/AI_WORKSPACE/browser/service.json")
BROWSER_SERVICE_NOT_RUNNING = (
    "Browser service is not running. Start it with: aegis browser serve"
)


class BrowserServiceUnavailable(RuntimeError):
    pass


class BrowserServiceClient:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        state_path: Path | str = DEFAULT_BROWSER_SERVICE_STATE_PATH,
    ):
        self.host = host
        self.port = port
        self.state_path = Path(state_path)

    def health(self) -> dict:
        return self._request("GET", "/health")

    def invoke(self, action: str, payload: dict) -> dict:
        response = self._request("POST", "/invoke", {"action": action, "payload": payload})
        if not response.get("success"):
            raise RuntimeError(str(response.get("error") or "Browser invocation failed"))
        output = response.get("output")
        return output if isinstance(output, dict) else {"result": output}

    def is_running(self) -> bool:
        try:
            self.health()
        except BrowserServiceUnavailable:
            return False
        return True

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self._base_url()}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError, KeyError) as exc:
            raise BrowserServiceUnavailable(BROWSER_SERVICE_NOT_RUNNING) from exc

    def _base_url(self) -> str:
        if self.host is not None or self.port is not None:
            return "http://{}:{}".format(
                self.host or DEFAULT_BROWSER_SERVICE_HOST,
                self.port or DEFAULT_BROWSER_SERVICE_PORT,
            )
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            return state.get("url") or f"http://{state['host']}:{state['port']}"
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return f"http://{DEFAULT_BROWSER_SERVICE_HOST}:{DEFAULT_BROWSER_SERVICE_PORT}"
