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
                AgentCapability(
                    id="browser.open",
                    description="Open a Firefox browser page.",
                    permissions=["browser.control"],
                    side_effects=["browser.launch", "network.navigate"],
                    metadata={
                        "name": "Browser Open",
                        "tags": ["browser", "playwright"],
                        "provider": "playwright",
                        "browser": "firefox",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "headless": {"type": "boolean"},
                            },
                        },
                        "output_schema": {"type": "object"},
                    },
                ),
                AgentCapability(
                    id="browser.navigate",
                    description="Navigate the active Firefox page to a URL.",
                    permissions=["browser.control"],
                    side_effects=["network.navigate"],
                    metadata={
                        "name": "Browser Navigate",
                        "tags": ["browser", "playwright"],
                        "provider": "playwright",
                        "browser": "firefox",
                        "input_schema": {
                            "type": "object",
                            "required": ["url"],
                            "properties": {"url": {"type": "string"}},
                        },
                        "output_schema": {"type": "object"},
                    },
                ),
                AgentCapability(
                    id="browser.extract.text",
                    description="Extract title, URL, and a text preview from the active page.",
                    permissions=["browser.read"],
                    metadata={
                        "name": "Browser Extract Text",
                        "tags": ["browser", "playwright", "extract"],
                        "provider": "playwright",
                        "browser": "firefox",
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                    },
                ),
                AgentCapability(
                    id="browser.screenshot",
                    description="Save a screenshot of the active browser page.",
                    permissions=["browser.read", "filesystem.write"],
                    side_effects=["filesystem.write"],
                    metadata={
                        "name": "Browser Screenshot",
                        "tags": ["browser", "playwright", "screenshot"],
                        "provider": "playwright",
                        "browser": "firefox",
                        "input_schema": {
                            "type": "object",
                            "properties": {"path": {"type": "string"}},
                        },
                        "output_schema": {"type": "object"},
                    },
                ),
                AgentCapability(
                    id="browser.close",
                    description="Close the active Playwright browser.",
                    permissions=["browser.control"],
                    side_effects=["browser.close"],
                    metadata={
                        "name": "Browser Close",
                        "tags": ["browser", "playwright"],
                        "provider": "playwright",
                        "browser": "firefox",
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                    },
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
        if capability_id == "browser.screenshot":
            path = payload.get("path")
            return self.provider.screenshot(str(path) if path else None)
        if capability_id == "browser.close":
            return self.provider.stop()
        raise ValueError(f"Unsupported capability: {capability_id}")
