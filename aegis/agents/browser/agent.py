import socket

from aegis.agents.runtime import (
    AgentCapability,
    AgentDescriptor,
    AgentHealth,
    AgentHealthState,
    AgentInvocation,
    AgentInvocationResult,
    BaseAgent,
)

from .playwright_provider import PlaywrightProvider


def _browser_capability(
    capability_id: str,
    description: str,
    *,
    permissions: list[str] | None = None,
    side_effects: list[str] | None = None,
    input_schema: dict | None = None,
    tags: list[str] | None = None,
) -> AgentCapability:
    name = capability_id.replace(".", " ").title()
    capability_tags = ["browser", "playwright"]
    if tags:
        capability_tags.extend(tags)
    return AgentCapability(
        id=capability_id,
        description=description,
        permissions=permissions or ["browser.control"],
        side_effects=side_effects or [],
        metadata={
            "name": name,
            "tags": capability_tags,
            "provider": "playwright",
            "browser": "firefox",
            "input_schema": input_schema or {"type": "object"},
            "output_schema": {"type": "object"},
        },
    )


class BrowserAgent(BaseAgent):
    """Local browser automation capability provider backed by Playwright."""

    def __init__(
        self,
        core=None,
        machine_id: str | None = None,
        provider: PlaywrightProvider | None = None,
    ):
        self.core = core
        self.provider = provider or PlaywrightProvider()
        self.descriptor = AgentDescriptor(
            id="browser-agent",
            name="Browser Agent",
            version="1",
            machine_id=machine_id or socket.gethostname(),
            capabilities=[
                _browser_capability(
                    "browser.open",
                    "Open a Firefox browser page.",
                    side_effects=["browser.launch", "network.navigate"],
                    input_schema={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "headless": {"type": "boolean"},
                        },
                    },
                ),
                _browser_capability(
                    "browser.navigate",
                    "Navigate the active Firefox page to a URL.",
                    side_effects=["network.navigate"],
                    input_schema={
                        "type": "object",
                        "required": ["url"],
                        "properties": {"url": {"type": "string"}},
                    },
                ),
                _browser_capability(
                    "browser.extract.text",
                    "Extract title, URL, and a text preview from the active page.",
                    permissions=["browser.read"],
                    tags=["extract"],
                ),
                _browser_capability(
                    "browser.inspect",
                    "Inspect DOM controls and readable page structure on the active page.",
                    permissions=["browser.read"],
                    tags=["inspect", "dom"],
                ),
                _browser_capability(
                    "browser.find",
                    "Find DOM elements by semantic text, role, placeholder, name, or tag.",
                    permissions=["browser.read"],
                    input_schema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "role": {"type": "string"},
                            "placeholder": {"type": "string"},
                            "name": {"type": "string"},
                            "tag": {"type": "string"},
                        },
                    },
                    tags=["find", "dom"],
                ),
                _browser_capability(
                    "browser.elements",
                    "List DOM elements discovered on the active page.",
                    permissions=["browser.read"],
                    input_schema={
                        "type": "object",
                        "properties": {"limit": {"type": "integer"}},
                    },
                    tags=["inspect", "dom"],
                ),
                _browser_capability(
                    "browser.forms",
                    "List forms and form fields on the active page.",
                    permissions=["browser.read"],
                    tags=["inspect", "forms", "dom"],
                ),
                _browser_capability(
                    "ui.tree",
                    "Build a provider-neutral UI tree from the active browser page.",
                    permissions=["browser.read"],
                    tags=["ui", "inspect", "accessibility"],
                ),
                _browser_capability(
                    "ui.describe",
                    "Describe the provider-neutral UI tree for the active browser page.",
                    permissions=["browser.read"],
                    tags=["ui", "inspect", "accessibility"],
                ),
                _browser_capability(
                    "ui.locate",
                    "Locate UI elements in the active browser page by accessible text.",
                    permissions=["browser.read"],
                    input_schema={
                        "type": "object",
                        "required": ["query"],
                        "properties": {"query": {"type": "string"}},
                    },
                    tags=["ui", "locate", "accessibility"],
                ),
                _browser_capability(
                    "browser.screenshot",
                    "Save a screenshot of the active browser page.",
                    permissions=["browser.read", "filesystem.write"],
                    side_effects=["filesystem.write"],
                    input_schema={
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                    },
                    tags=["screenshot"],
                ),
                _browser_capability(
                    "browser.close",
                    "Close the active Playwright browser.",
                    side_effects=["browser.close"],
                ),
                _browser_capability(
                    "browser.click",
                    "Click an element on the active browser page.",
                    side_effects=["browser.interact"],
                    input_schema={
                        "type": "object",
                        "required": ["selector"],
                        "properties": {"selector": {"type": "string"}},
                    },
                ),
                _browser_capability(
                    "browser.fill",
                    "Fill a form field on the active browser page.",
                    side_effects=["browser.interact"],
                    input_schema={
                        "type": "object",
                        "required": ["selector", "value"],
                        "properties": {
                            "selector": {"type": "string"},
                            "value": {"type": "string"},
                        },
                    },
                ),
                _browser_capability(
                    "browser.press",
                    "Press a keyboard key on the active browser page.",
                    side_effects=["browser.interact"],
                    input_schema={
                        "type": "object",
                        "required": ["key"],
                        "properties": {"key": {"type": "string"}},
                    },
                ),
                _browser_capability(
                    "browser.wait",
                    "Wait for an element or a timeout on the active browser page.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string"},
                            "timeout_ms": {"type": "integer"},
                        },
                    },
                ),
                _browser_capability(
                    "browser.select",
                    "Select an option in a form field on the active browser page.",
                    side_effects=["browser.interact"],
                    input_schema={
                        "type": "object",
                        "required": ["selector", "value"],
                        "properties": {
                            "selector": {"type": "string"},
                            "value": {"type": "string"},
                        },
                    },
                ),
                _browser_capability(
                    "browser.tabs.list",
                    "List tabs in the active browser context.",
                    permissions=["browser.read"],
                    tags=["tabs"],
                ),
                _browser_capability(
                    "browser.tabs.switch",
                    "Switch the active browser tab.",
                    input_schema={
                        "type": "object",
                        "required": ["index"],
                        "properties": {"index": {"type": "integer"}},
                    },
                    tags=["tabs"],
                ),
                _browser_capability(
                    "browser.tabs.close",
                    "Close a browser tab.",
                    side_effects=["browser.close_tab"],
                    input_schema={
                        "type": "object",
                        "properties": {"index": {"type": "integer"}},
                    },
                    tags=["tabs"],
                ),
                _browser_capability(
                    "browser.download",
                    "Prepare the active page for browser downloads.",
                    side_effects=["browser.download"],
                    tags=["download"],
                ),
                _browser_capability(
                    "browser.upload",
                    "Upload a file through a file input on the active browser page.",
                    permissions=["browser.control", "filesystem.read"],
                    side_effects=["browser.upload"],
                    input_schema={
                        "type": "object",
                        "required": ["selector", "path"],
                        "properties": {
                            "selector": {"type": "string"},
                            "path": {"type": "string"},
                        },
                    },
                    tags=["upload"],
                ),
            ],
            health=AgentHealth(AgentHealthState.healthy, message="Ready"),
            metadata={"runtime": "builtin", "provider": "playwright", "browser": "firefox"},
        )

    def stop(self, reason: str = "") -> AgentDescriptor:
        self.provider.stop()
        return super().stop(reason=reason)

    def invoke(self, invocation: AgentInvocation) -> AgentInvocationResult:
        try:
            output = self._invoke(invocation.capability_id, invocation.payload)
        except Exception as exc:
            return AgentInvocationResult(
                success=False,
                error=str(exc),
                metadata={"capability_id": invocation.capability_id},
            )
        return AgentInvocationResult(success=True, output=output)

    def _invoke(self, capability_id: str, payload: dict) -> dict:
        if capability_id == "browser.open":
            headless = bool(payload.get("headless", False))
            self.provider.start(headless=headless, browser="firefox")
            return self.provider.open(payload.get("url"))
        if capability_id == "browser.navigate":
            url = payload.get("url")
            if not url:
                raise ValueError("browser.navigate requires payload.url")
            return self.provider.navigate(str(url))
        if capability_id == "browser.extract.text":
            return self.provider.extract_text()
        if capability_id == "browser.inspect":
            return self.provider.inspect()
        if capability_id == "browser.find":
            query = {
                key: payload[key]
                for key in ("text", "role", "placeholder", "name", "tag")
                if payload.get(key) not in (None, "")
            }
            if not query:
                raise ValueError("browser.find requires at least one search field")
            return self.provider.find(query)
        if capability_id == "browser.elements":
            return self.provider.elements(int(payload.get("limit", 50)))
        if capability_id == "browser.forms":
            return self.provider.forms()
        if capability_id == "ui.tree":
            return self.provider.ui_tree()
        if capability_id == "ui.describe":
            return self.provider.ui_describe()
        if capability_id == "ui.locate":
            return self.provider.ui_locate(self._required(payload, "query", capability_id))
        if capability_id == "browser.screenshot":
            path = payload.get("path")
            return self.provider.screenshot(str(path) if path else None)
        if capability_id == "browser.close":
            return self.provider.stop()
        if capability_id == "browser.click":
            return self.provider.click(self._required(payload, "selector", capability_id))
        if capability_id == "browser.fill":
            return self.provider.fill(
                self._required(payload, "selector", capability_id),
                self._required(payload, "value", capability_id),
            )
        if capability_id == "browser.press":
            return self.provider.press(self._required(payload, "key", capability_id))
        if capability_id == "browser.wait":
            timeout_ms = int(payload.get("timeout_ms", 30000))
            selector = payload.get("selector")
            return self.provider.wait_for(str(selector) if selector else None, timeout_ms)
        if capability_id == "browser.select":
            return self.provider.select(
                self._required(payload, "selector", capability_id),
                self._required(payload, "value", capability_id),
            )
        if capability_id == "browser.tabs.list":
            return self.provider.list_tabs()
        if capability_id == "browser.tabs.switch":
            return self.provider.switch_tab(int(self._required(payload, "index", capability_id)))
        if capability_id == "browser.tabs.close":
            index = payload.get("index")
            return self.provider.close_tab(int(index) if index is not None else None)
        if capability_id == "browser.download":
            return self.provider.download_start()
        if capability_id == "browser.upload":
            return self.provider.upload(
                self._required(payload, "selector", capability_id),
                self._required(payload, "path", capability_id),
            )
        raise ValueError(f"Unsupported capability: {capability_id}")

    def _required(self, payload: dict, key: str, capability_id: str) -> str:
        value = payload.get(key)
        if value is None or value == "":
            raise ValueError(f"{capability_id} requires payload.{key}")
        return str(value)
