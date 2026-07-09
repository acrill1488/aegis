from aegis.agents.browser import BrowserAgent
from aegis.agents.runtime import AgentRuntime
from aegis.capabilities import CapabilityInvocationRequest, CapabilityRuntime


class FakePlaywrightProvider:
    def __init__(self):
        self.started = []
        self.opened = []
        self.stopped = False

    def start(self, headless=False, browser="firefox"):
        self.started.append({"headless": headless, "browser": browser})
        return self.status()

    def stop(self):
        self.stopped = True
        return self.status()

    def open(self, url=None):
        self.opened.append(url)
        return {"url": url or "about:blank", "title": "Example"}

    def navigate(self, url):
        return {"url": url, "title": "Example"}

    def extract_text(self):
        return {"title": "Example", "url": "https://example.test", "text_preview": "Hello"}

    def screenshot(self, path=None):
        return {"path": path or "F:/AI_WORKSPACE/browser/screenshots/screenshot-test.png"}

    def status(self):
        return {"running": bool(self.started), "stopped": self.stopped}


class Core:
    events = None


def test_browser_agent_capabilities_are_auto_discovered():
    provider = FakePlaywrightProvider()
    agent = BrowserAgent(provider=provider, machine_id="test-machine")
    core = Core()
    core.agent_runtime = AgentRuntime(core)
    core.capability_runtime = CapabilityRuntime(core)

    core.agent_runtime.register(agent)

    descriptors = {descriptor.id: descriptor for descriptor in core.capability_runtime.list()}
    assert {
        "browser.open",
        "browser.navigate",
        "browser.extract.text",
        "browser.screenshot",
        "browser.close",
    } <= set(descriptors)
    assert descriptors["browser.open"].owner_agent == "browser-agent"
    assert descriptors["browser.open"].metadata["browser"] == "firefox"


def test_browser_open_invokes_firefox_provider_through_capability_runtime():
    provider = FakePlaywrightProvider()
    agent = BrowserAgent(provider=provider, machine_id="test-machine")
    core = Core()
    core.agent_runtime = AgentRuntime(core)
    core.capability_runtime = CapabilityRuntime(core)
    core.agent_runtime.register(agent)

    result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="browser.open",
            payload={"url": "https://example.test", "headless": True},
        )
    )

    assert result.success is True
    assert result.output == {"url": "https://example.test", "title": "Example"}
    assert provider.started == [{"headless": True, "browser": "firefox"}]
    assert provider.opened == ["https://example.test"]
