import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aegis.agents.browser.client import BrowserServiceClient, BrowserServiceUnavailable
from aegis.agents.browser.service import BrowserService


class FakeProvider:
    def __init__(self):
        self.started = []
        self.stopped = False

    def start(self, headless=False, browser="firefox"):
        self.started.append({"headless": headless, "browser": browser})
        return self.status()

    def stop(self):
        self.stopped = True
        return self.status()

    def open(self, url=None):
        return {"url": url or "about:blank", "title": "Example"}

    def navigate(self, url):
        return {"url": url, "title": "Example"}

    def extract_text(self):
        return {"text_preview": "Hello"}

    def inspect(self):
        return {"url": "https://example.test", "inputs": []}

    def find(self, query):
        return {"matches": [{"query": query}], "best_match": {"query": query}}

    def elements(self, limit=50):
        return {"elements": [{"tag": "input"}], "limit": limit}

    def forms(self):
        return {"forms": []}

    def ui_tree(self):
        return {"root": {"id": "ui-0"}, "provider": "browser.playwright"}

    def ui_observe(self):
        return {"source": "browser.dom", "elements": []}

    def ui_describe(self):
        return {"element_count": 1}

    def ui_locate(self, query):
        return {"query": query, "best_match": {"name": query}}

    def screenshot(self, path=None):
        return {"path": path or "screenshot.png"}

    def click(self, selector):
        return {"clicked": selector}

    def fill(self, selector, value):
        return {"filled": selector, "value": value}

    def press(self, key):
        return {"pressed": key}

    def wait_for(self, selector=None, timeout_ms=30000):
        return {"selector": selector, "timeout_ms": timeout_ms}

    def select(self, selector, value):
        return {"selected": [value], "selector": selector}

    def list_tabs(self):
        return {"tabs": [{"index": 0, "active": True}]}

    def switch_tab(self, index):
        return {"index": index}

    def close_tab(self, index=None):
        return {"closed_index": index}

    def status(self):
        return {"running": bool(self.started) and not self.stopped}


def test_browser_service_invokes_actions_against_owned_provider():
    provider = FakeProvider()
    service = BrowserService(provider=provider, headless=True)

    service.start()
    result = service.invoke("navigate", {"url": "https://example.test"})

    assert provider.started == [{"headless": True, "browser": "firefox"}]
    assert result == {"url": "https://example.test", "title": "Example"}
    assert service.health()["healthy"] is True


def test_browser_close_action_keeps_service_available():
    provider = FakeProvider()
    service = BrowserService(provider=provider)

    service.start()
    close_result = service.invoke("close", {})
    reopen_result = service.invoke("open", {"url": "https://example.test"})

    assert close_result["running"] is False
    assert reopen_result == {"url": "https://example.test", "title": "Example"}
    assert service.status.value == "running"


def test_browser_service_invokes_dom_inspection_actions():
    provider = FakeProvider()
    service = BrowserService(provider=provider)

    inspect_result = service.invoke("inspect", {})
    find_result = service.invoke("find", {"placeholder": "Search"})
    elements_result = service.invoke("elements", {"limit": 5})
    forms_result = service.invoke("forms", {})
    ui_tree_result = service.invoke("ui_tree", {})
    ui_observe_result = service.invoke("ui_observe", {})
    ui_describe_result = service.invoke("ui_describe", {})
    ui_locate_result = service.invoke("ui_locate", {"query": "Search"})

    assert inspect_result == {"url": "https://example.test", "inputs": []}
    assert find_result["best_match"] == {"query": {"placeholder": "Search"}}
    assert elements_result == {"elements": [{"tag": "input"}], "limit": 5}
    assert forms_result == {"forms": []}
    assert ui_tree_result["provider"] == "browser.playwright"
    assert ui_observe_result["source"] == "browser.dom"
    assert ui_describe_result == {"element_count": 1}
    assert ui_locate_result["best_match"] == {"name": "Search"}


def test_browser_service_client_invokes_http_service(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            response = {
                "success": True,
                "output": {
                    "action": request["action"],
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

    try:
        result = BrowserServiceClient(
            host="127.0.0.1",
            port=server.server_address[1],
            state_path=tmp_path / "missing.json",
        ).invoke("click", {"selector": "#submit"})
    finally:
        server.shutdown()
        server.server_close()

    assert result == {"action": "click", "payload": {"selector": "#submit"}}


def test_browser_service_client_reports_unavailable_service(tmp_path):
    client = BrowserServiceClient(
        host="127.0.0.1",
        port=9,
        state_path=tmp_path / "missing.json",
    )

    with pytest.raises(BrowserServiceUnavailable) as exc:
        client.invoke("tabs", {})

    assert str(exc.value) == (
        "Browser service is not running. Start it with: aegis browser serve"
    )
