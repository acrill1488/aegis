from pathlib import Path

from aegis.scenarios import Scenario, ScenarioRegistry, ScenarioRuntime, ScenarioStep


class FakeIPCClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests = []

    def request(self, target, action, payload=None):
        self.requests.append((target, action, payload or {}))
        if self.outputs:
            output = self.outputs.pop(0)
            if isinstance(output, Exception):
                raise output
            return output
        return {"success": True}


def test_scenario_registry_seeds_defaults():
    registry = ScenarioRegistry()
    registry.seed_defaults()

    ids = [scenario.id for scenario in registry.list()]

    assert ids == ["browser.wikipedia.observe", "browser.wikipedia.search"]
    assert registry.get("browser.wikipedia.search").steps[2].action == "browser.fill"


def test_scenario_runtime_runs_steps_through_ipc_and_writes_report(tmp_path):
    registry = ScenarioRegistry()
    registry.register(
        Scenario(
            id="sample",
            name="Sample",
            steps=[
                ScenarioStep(
                    id="open",
                    action="browser.open",
                    payload={"url": "https://example.test"},
                    expect={"url_contains": "example.test"},
                ),
                ScenarioStep(
                    id="locate",
                    action="ui.locate",
                    payload={"query": "Search"},
                    expect={"element_exists": True},
                ),
            ],
        )
    )
    ipc = FakeIPCClient(
        [
            {"url": "https://example.test", "title": "Example"},
            {"best_match": {"name": "Search"}, "matches": [{"name": "Search"}]},
        ]
    )
    runtime = ScenarioRuntime(registry=registry, ipc_client=ipc, report_dir=tmp_path)

    result = runtime.run("sample")

    assert result.success is True
    assert ipc.requests == [
        ("browser", "open", {"url": "https://example.test"}),
        ("ui", "locate", {"query": "Search"}),
    ]
    assert Path(result.metadata["report_path"]).exists()


def test_scenario_runtime_stops_on_failed_expectation(tmp_path):
    registry = ScenarioRegistry()
    registry.register(
        Scenario(
            id="sample",
            name="Sample",
            steps=[
                ScenarioStep(
                    id="read",
                    action="browser.text",
                    expect={"contains_text": "AEGIS"},
                ),
                ScenarioStep(id="screenshot", action="browser.screenshot"),
            ],
        )
    )
    runtime = ScenarioRuntime(
        registry=registry,
        ipc_client=FakeIPCClient([{"text_preview": "Other text"}]),
        report_dir=tmp_path,
    )

    result = runtime.run("sample")

    assert result.success is False
    assert len(result.step_results) == 1
    assert "Expected output to contain text" in result.error


def test_scenario_expect_validators():
    runtime = ScenarioRuntime(ipc_client=FakeIPCClient([]))

    validation = runtime.validate_expect(
        {
            "success": True,
            "url": "https://example.test/wiki/AEGIS",
            "title": "AEGIS - Example",
            "text_preview": "About AEGIS",
            "best_match": {"name": "AEGIS"},
        },
        {
            "success_true": True,
            "url_contains": "/wiki/",
            "title_contains": "AEGIS",
            "contains_text": "About",
            "element_exists": True,
        },
    )

    assert validation == {"success": True, "errors": []}


def test_scenario_runtime_filters_ui_locate_output_by_role(tmp_path):
    registry = ScenarioRegistry()
    registry.register(
        Scenario(
            id="sample",
            name="Sample",
            steps=[
                ScenarioStep(
                    id="locate",
                    action="ui.locate",
                    payload={"query": "search", "role": "textbox"},
                    expect={"element_exists": True},
                ),
            ],
        )
    )
    runtime = ScenarioRuntime(
        registry=registry,
        ipc_client=FakeIPCClient(
            [
                {
                    "best_match": {
                        "role": "button",
                        "selector": {"type": "text", "value": {"text": "Search"}},
                    },
                    "matches": [
                        {
                            "role": "button",
                            "selector": {"type": "text", "value": {"text": "Search"}},
                        },
                        {"role": "textbox", "selector": "#searchInput"},
                    ],
                }
            ]
        ),
        report_dir=tmp_path,
    )

    result = runtime.run("sample")

    output = result.step_results[0]["output"]
    assert result.success is True
    assert output["best_match"] == {"role": "textbox", "selector": "#searchInput"}
    assert output["matches"] == [{"role": "textbox", "selector": "#searchInput"}]
