from aegis.agents.browser import BrowserAgent
from aegis.agents.runtime import AgentRuntime
from aegis.capabilities import CapabilityInvocationRequest, CapabilityRuntime


class FakePlaywrightProvider:
    def __init__(self):
        self.started = []
        self.opened = []
        self.clicked = []
        self.filled = []
        self.pressed = []
        self.selected = []
        self.switched_tabs = []
        self.closed_tabs = []
        self.uploaded = []
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

    def inspect(self):
        return {"url": "https://example.test", "inputs": [{"name": "Search"}]}

    def find(self, query):
        return {
            "matches": [{"tag": "input", "query": query}],
            "best_match": {"tag": "input", "query": query},
            "suggested_selector": 'input[name="q"]',
        }

    def elements(self, limit=50):
        return {"elements": [{"tag": "input", "name": "Search"}], "limit": limit}

    def forms(self):
        return {"forms": [{"index": 0, "inputs": []}]}

    def ui_tree(self):
        return {
            "provider": "browser.playwright",
            "source": "https://example.test",
            "root": {"id": "ui-0", "role": "WebArea", "name": "Example"},
        }

    def ui_describe(self):
        return {"element_count": 1, "interactive": []}

    def ui_locate(self, query, role=None):
        return {
            "query": query,
            "role": role,
            "best_match": {"id": "ui-0.1", "name": query, "role": role},
        }

    def screenshot(self, path=None):
        return {"path": path or "F:/AI_WORKSPACE/browser/screenshots/screenshot-test.png"}

    def click(self, selector):
        self.clicked.append(selector)
        return {"url": "https://example.test", "title": "Example"}

    def fill(self, selector, value):
        self.filled.append({"selector": selector, "value": value})
        return {"url": "https://example.test", "title": "Example"}

    def press(self, key):
        self.pressed.append(key)
        return {"url": "https://example.test", "title": "Example"}

    def wait_for(self, selector=None, timeout_ms=30000):
        return {"selector": selector, "timeout_ms": timeout_ms}

    def select(self, selector, value):
        self.selected.append({"selector": selector, "value": value})
        return {"selected": [value], "url": "https://example.test", "title": "Example"}

    def list_tabs(self):
        return {"tabs": [{"index": 0, "url": "https://example.test", "active": True}]}

    def switch_tab(self, index):
        self.switched_tabs.append(index)
        return {"index": index, "url": "https://example.test", "title": "Example"}

    def close_tab(self, index=None):
        self.closed_tabs.append(index)
        return {"closed": True, "closed_index": index}

    def download_start(self):
        return {"listening": True, "downloads": []}

    def upload(self, selector, path):
        self.uploaded.append({"selector": selector, "path": path})
        return {"selector": selector, "path": path}

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
        "browser.inspect",
        "browser.find",
        "browser.elements",
        "browser.forms",
        "ui.tree",
        "ui.describe",
        "ui.locate",
        "browser.screenshot",
        "browser.close",
        "browser.click",
        "browser.fill",
        "browser.press",
        "browser.wait",
        "browser.select",
        "browser.tabs.list",
        "browser.tabs.switch",
        "browser.tabs.close",
        "browser.download",
        "browser.upload",
    } <= set(descriptors)
    assert descriptors["browser.open"].owner_agent == "browser-agent"
    assert descriptors["browser.open"].metadata["browser"] == "firefox"
    assert descriptors["browser.click"].permissions == ["browser.control"]
    assert descriptors["browser.inspect"].permissions == ["browser.read"]
    assert descriptors["ui.tree"].permissions == ["browser.read"]
    assert descriptors["ui.locate"].metadata["provider"] == "playwright"
    assert descriptors["browser.upload"].permissions == [
        "browser.control",
        "filesystem.read",
    ]


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


def test_browser_interaction_capabilities_invoke_provider_through_runtime():
    provider = FakePlaywrightProvider()
    agent = BrowserAgent(provider=provider, machine_id="test-machine")
    core = Core()
    core.agent_runtime = AgentRuntime(core)
    core.capability_runtime = CapabilityRuntime(core)
    core.agent_runtime.register(agent)

    click_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="browser.click",
            payload={"selector": "#submit"},
        )
    )
    fill_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="browser.fill",
            payload={"selector": "#email", "value": "user@example.test"},
        )
    )
    tab_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="browser.tabs.switch",
            payload={"index": 0},
        )
    )

    assert click_result.success is True
    assert fill_result.success is True
    assert tab_result.success is True
    assert provider.clicked == ["#submit"]
    assert provider.filled == [{"selector": "#email", "value": "user@example.test"}]
    assert provider.switched_tabs == [0]


def test_browser_dom_capabilities_invoke_provider_through_runtime():
    provider = FakePlaywrightProvider()
    agent = BrowserAgent(provider=provider, machine_id="test-machine")
    core = Core()
    core.agent_runtime = AgentRuntime(core)
    core.capability_runtime = CapabilityRuntime(core)
    core.agent_runtime.register(agent)

    inspect_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(capability_id="browser.inspect", payload={})
    )
    find_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="browser.find",
            payload={"placeholder": "Search"},
        )
    )
    elements_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="browser.elements",
            payload={"limit": 5},
        )
    )
    forms_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(capability_id="browser.forms", payload={})
    )

    assert inspect_result.success is True
    assert inspect_result.output["inputs"] == [{"name": "Search"}]
    assert find_result.success is True
    assert find_result.output["suggested_selector"] == 'input[name="q"]'
    assert elements_result.output["limit"] == 5
    assert forms_result.output == {"forms": [{"index": 0, "inputs": []}]}


def test_browser_ui_capabilities_invoke_provider_through_runtime():
    provider = FakePlaywrightProvider()
    agent = BrowserAgent(provider=provider, machine_id="test-machine")
    core = Core()
    core.agent_runtime = AgentRuntime(core)
    core.capability_runtime = CapabilityRuntime(core)
    core.agent_runtime.register(agent)

    tree_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(capability_id="ui.tree", payload={})
    )
    describe_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(capability_id="ui.describe", payload={})
    )
    locate_result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="ui.locate",
            payload={"query": "Search", "role": "textbox"},
        )
    )

    assert tree_result.success is True
    assert tree_result.output["root"]["role"] == "WebArea"
    assert describe_result.output["element_count"] == 1
    assert locate_result.output["best_match"]["name"] == "Search"
    assert locate_result.output["best_match"]["role"] == "textbox"
