from __future__ import annotations

from typing import Callable

from aegis.services import BaseService, ServiceStatus

from .playwright_provider import PlaywrightProvider


class BrowserService(BaseService):
    def __init__(
        self,
        provider: PlaywrightProvider | None = None,
        *,
        headless: bool = False,
    ):
        super().__init__("browser-service", "Browser Service")
        self.provider = provider or PlaywrightProvider()
        self.headless = headless

    def start(self) -> dict:
        self.status = ServiceStatus.starting
        self.provider.start(headless=self.headless, browser="firefox")
        self.status = ServiceStatus.running
        return self.status_dict()

    def stop(self) -> dict:
        self.status = ServiceStatus.stopping
        result = self.provider.stop()
        self.status = ServiceStatus.stopped
        return {"service": self.status_dict(), "provider": result}

    def invoke(self, action: str, payload: dict) -> dict:
        handler = self._action_handlers().get(action)
        if handler is None:
            raise ValueError(f"Unsupported browser action: {action}")
        return handler(payload)

    def health(self) -> dict:
        provider_status = self.provider.status()
        healthy = self.status == ServiceStatus.running and bool(provider_status.get("running"))
        return {
            **self.status_dict(),
            "healthy": healthy,
            "provider": provider_status,
        }

    def status_dict(self) -> dict:
        return {
            **super().status_dict(),
            "headless": self.headless,
        }

    def _action_handlers(self) -> dict[str, Callable[[dict], dict]]:
        return {
            "open": self._open,
            "navigate": self._navigate,
            "click": self._click,
            "fill": self._fill,
            "press": self._press,
            "wait": self._wait,
            "select": self._select,
            "text": self._text,
            "inspect": self._inspect,
            "find": self._find,
            "elements": self._elements,
            "forms": self._forms,
            "ui_tree": self._ui_tree,
            "ui_observe": self._ui_observe,
            "ui_describe": self._ui_describe,
            "ui_locate": self._ui_locate,
            "screenshot": self._screenshot,
            "tabs": self._tabs,
            "switch_tab": self._switch_tab,
            "close_tab": self._close_tab,
            "close": self._close,
        }

    def _open(self, payload: dict) -> dict:
        if "headless" in payload:
            self.headless = bool(payload["headless"])
        if not self.provider.status().get("running"):
            self.provider.start(headless=self.headless, browser="firefox")
        self.status = ServiceStatus.running
        return self.provider.open(payload.get("url"))

    def _navigate(self, payload: dict) -> dict:
        url = payload.get("url")
        if not url:
            raise ValueError("navigate requires payload.url")
        return self.provider.navigate(str(url))

    def _click(self, payload: dict) -> dict:
        return self.provider.click(self._required(payload, "selector", "click"))

    def _fill(self, payload: dict) -> dict:
        return self.provider.fill(
            self._required(payload, "selector", "fill"),
            self._required(payload, "value", "fill"),
        )

    def _press(self, payload: dict) -> dict:
        return self.provider.press(self._required(payload, "key", "press"))

    def _wait(self, payload: dict) -> dict:
        selector = payload.get("selector")
        timeout_ms = int(payload.get("timeout_ms", 30000))
        return self.provider.wait_for(str(selector) if selector else None, timeout_ms)

    def _select(self, payload: dict) -> dict:
        return self.provider.select(
            self._required(payload, "selector", "select"),
            self._required(payload, "value", "select"),
        )

    def _text(self, payload: dict) -> dict:
        return self.provider.extract_text()

    def _inspect(self, payload: dict) -> dict:
        return self.provider.inspect()

    def _find(self, payload: dict) -> dict:
        query = {
            key: payload[key]
            for key in ("text", "role", "placeholder", "name", "tag")
            if payload.get(key) not in (None, "")
        }
        if not query:
            raise ValueError("find requires at least one search field")
        return self.provider.find(query)

    def _elements(self, payload: dict) -> dict:
        return self.provider.elements(int(payload.get("limit", 50)))

    def _forms(self, payload: dict) -> dict:
        return self.provider.forms()

    def _ui_tree(self, payload: dict) -> dict:
        return self.provider.ui_tree()

    def _ui_observe(self, payload: dict) -> dict:
        return self.provider.ui_observe()

    def _ui_describe(self, payload: dict) -> dict:
        return self.provider.ui_describe()

    def _ui_locate(self, payload: dict) -> dict:
        query = self._required(payload, "query", "ui_locate")
        return self.provider.ui_locate(query)

    def _screenshot(self, payload: dict) -> dict:
        path = payload.get("path")
        return self.provider.screenshot(str(path) if path else None)

    def _tabs(self, payload: dict) -> dict:
        return self.provider.list_tabs()

    def _switch_tab(self, payload: dict) -> dict:
        return self.provider.switch_tab(int(self._required(payload, "index", "switch_tab")))

    def _close_tab(self, payload: dict) -> dict:
        index = payload.get("index")
        return self.provider.close_tab(int(index) if index is not None else None)

    def _close(self, payload: dict) -> dict:
        result = self.provider.stop()
        if self.status == ServiceStatus.stopped:
            self.status = ServiceStatus.running
        return result

    def _required(self, payload: dict, key: str, action: str) -> str:
        value = payload.get(key)
        if value is None or value == "":
            raise ValueError(f"{action} requires payload.{key}")
        return str(value)
