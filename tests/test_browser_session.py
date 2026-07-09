import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aegis.agents.browser.session import BrowserSessionClient, BrowserSessionUnavailable


def test_browser_session_client_invokes_active_session(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            response = {
                "success": True,
                "output": {
                    "capability_id": request["capability_id"],
                    "payload": request["payload"],
                },
            }
            body = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": server.server_address[1],
            }
        ),
        encoding="utf-8",
    )

    try:
        result = BrowserSessionClient(session_path).invoke(
            "browser.click",
            {"selector": "#submit"},
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result == {
        "capability_id": "browser.click",
        "payload": {"selector": "#submit"},
    }


def test_browser_session_client_reports_missing_session(tmp_path):
    client = BrowserSessionClient(tmp_path / "missing-session.json")

    with pytest.raises(BrowserSessionUnavailable) as exc:
        client.invoke("browser.tabs.list", {})

    assert str(exc.value) == (
        "Browser session is not running. Start it with: aegis browser serve"
    )
