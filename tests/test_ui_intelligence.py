from aegis.capabilities import CapabilityInvocationRequest, CapabilityRuntime
from aegis.services import ServiceRuntime
from aegis.ui_intelligence import UIIntelligenceRuntime
from aegis.ui_intelligence.providers import BrowserObservationProvider


class FakeBrowser:
    def health(self):
        return {"provider": {"url": "https://example.test"}}

    def invoke(self, action, payload):
        if action == "inspect":
            return {
                "url": "https://example.test",
                "title": "Example",
                "inputs": [
                    {
                        "tag": "input",
                        "type": "search",
                        "placeholder": "Search docs",
                        "text": "",
                        "selector": "#q",
                        "visible": True,
                    },
                    {
                        "tag": "input",
                        "type": "hidden",
                        "name": "csrf",
                        "visible": True,
                    },
                    {
                        "tag": "button",
                        "text": "x" * 201,
                        "visible": True,
                    },
                ],
                "buttons": [
                    {
                        "tag": "button",
                        "text": "Submit",
                        "selector": "#submit",
                        "visible": True,
                    }
                ],
                "links": [
                    {
                        "tag": "a",
                        "text": "Docs",
                        "selector": "a",
                        "visible": True,
                    }
                ],
                "headings": [
                    {"tag": "h1", "text": "Welcome", "visible": True},
                    {"tag": "h4", "text": "Minor", "visible": True},
                ],
            }
        if action == "forms":
            return {"forms": []}
        return {}


class FakeServiceRegistry:
    def __init__(self, service):
        self.service = service

    def get(self, service_id):
        return self.service if service_id == "browser-service" else None


class FakeCore:
    def __init__(self, service):
        self.events = None
        self.registry = FakeRuntimeRegistry(self)
        self.service_runtime = ServiceRuntime(self, registry=FakeServiceRegistry(service))
        self.capability_runtime = CapabilityRuntime(self)


class FakeRuntimeRegistry:
    def __init__(self, core):
        self.core = core
        self.services = {}

    def register(self, name, service):
        self.services[name] = service

    def get(self, name):
        return self.services.get(name)


def test_browser_observation_provider_filters_dom_noise_and_builds_actions():
    observation = BrowserObservationProvider(FakeBrowser()).observe()

    roles = [element.role for element in observation.elements]
    names = [element.name for element in observation.elements]

    assert roles == ["textbox", "button", "link", "heading"]
    assert "Search docs" in names
    assert "Submit" in names
    assert "Current page: Example (https://example.test)" in observation.summary
    assert {"type": "fill", "target": "ui-0", "selector": "#q"} in observation.actions
    assert {"type": "click", "target": "ui-1", "selector": "#submit"} in observation.actions


def test_ui_intelligence_runtime_locates_elements_and_registers_capabilities():
    core = FakeCore(FakeBrowser())
    runtime = UIIntelligenceRuntime(core)
    core.registry.register("ui_intelligence", runtime)
    runtime.register_capabilities()

    located = runtime.locate("Search")
    result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="ui.locate",
            payload={"query": "Submit"},
        )
    )

    assert located["best_match"]["role"] == "textbox"
    assert result.success is True
    assert result.output["best_match"]["role"] == "button"
    assert core.capability_runtime.resolve("ui.observe")["provider_type"] == "runtime"
