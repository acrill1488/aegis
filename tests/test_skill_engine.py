from pathlib import Path

from aegis.recovery_engine import RecoveryEngineRuntime
from aegis.skill_engine import SkillEngineRuntime, SkillLoader, SkillRegistry
from aegis.skill_engine.models import Skill, SkillNode


DAEMON_NOT_RUNNING = "AEGIS daemon is not running. Start it with: aegis daemon serve"


class FakeScenarioRuntime:
    def __init__(self):
        self.steps = []

    def run_step(self, step):
        self.steps.append(step)
        if step.action == "ui.locate":
            output = {
                    "best_match": {"selector": "#searchInput", "role": "textbox"},
                    "matches": [{"selector": "#searchInput", "role": "textbox"}],
                }
        elif step.action == "browser.text":
            output = {"text_preview": "AEGIS encyclopedia page"}
        else:
            output = {"success": True, **step.payload}
        return {
            "step_id": step.id,
            "action": step.action,
            "success": True,
            "payload": step.payload,
            "output": output,
            "validation": {"success": True, "errors": []},
        }


class FailingScenarioRuntime:
    def run_step(self, step):
        raise RuntimeError(DAEMON_NOT_RUNNING)


class FakeCore:
    def __init__(self):
        self.scenario_runtime = FakeScenarioRuntime()


def test_skill_loader_loads_yaml_steps_and_inputs(tmp_path):
    skill_file = tmp_path / "sample.yaml"
    skill_file.write_text(
        """
id: sample.skill
name: Sample Skill
input:
  - query
steps:
  - id: open
    action: browser.open
    payload:
      url: https://example.test
  - ui.locate Search
edges:
  - [open, ui-locate-2]
metadata:
  tags: [sample]
""",
        encoding="utf-8",
    )

    skill = SkillLoader().load_file(skill_file)

    assert skill.id == "sample.skill"
    assert skill.inputs == {"query": {}}
    assert [node.action for node in skill.nodes] == ["browser.open", "ui.locate"]
    assert skill.nodes[1].payload == {"query": "Search"}


def test_skill_runtime_substitutes_inputs_and_node_outputs(tmp_path):
    registry = SkillRegistry(default_root=tmp_path)
    skill = SkillLoader().load_file(
        Path("F:/AI_WORKSPACE/skills/browser/wikipedia.search.yaml")
    )
    registry.register(skill)
    runtime = SkillEngineRuntime(FakeCore(), registry=registry)

    result = runtime.run("browser.wikipedia.search", {"query": "AEGIS"})

    assert result.success is True
    assert [step.action for step in runtime.core.scenario_runtime.steps] == [
        "browser.open",
        "ui.locate",
        "browser.fill",
        "browser.press",
        "browser.wait",
        "browser.text",
    ]
    fill_step = runtime.core.scenario_runtime.steps[2]
    assert fill_step.payload == {"selector": "#searchInput", "value": "AEGIS"}
    locate_step = runtime.core.scenario_runtime.steps[1]
    assert locate_step.payload == {"query": "search", "role": "textbox"}


def test_skill_runtime_validate_reports_bad_edges(tmp_path):
    registry = SkillRegistry(default_root=tmp_path)
    skill = SkillLoader().load_file(
        Path("F:/AI_WORKSPACE/skills/browser/wikipedia.observe.yaml")
    )
    skill.edges.append(["missing", "locate-search"])
    registry.register(skill)
    runtime = SkillEngineRuntime(FakeCore(), registry=registry)

    result = runtime.validate("browser.wikipedia.observe")

    assert result["success"] is False
    assert "Edge references missing source node: missing" in result["errors"]


def test_skill_runtime_dry_run_skips_expect_validation(tmp_path):
    registry = SkillRegistry(default_root=tmp_path)
    skill = SkillLoader().load_file(
        Path("F:/AI_WORKSPACE/skills/browser/wikipedia.search.yaml")
    )
    registry.register(skill)
    runtime = SkillEngineRuntime(FakeCore(), registry=registry)

    result = runtime.dry_run("browser.wikipedia.search", {"query": "AEGIS"})

    assert result.success is True
    assert result.metadata["dry_run"] is True
    assert result.node_results[-1]["validation"]["skipped"] is True
    assert runtime.core.scenario_runtime.steps == []


def test_skill_runtime_reports_daemon_not_running(tmp_path):
    registry = SkillRegistry(default_root=tmp_path)
    skill = SkillLoader().load_file(
        Path("F:/AI_WORKSPACE/skills/browser/wikipedia.observe.yaml")
    )
    registry.register(skill)
    core = FakeCore()
    core.scenario_runtime = FailingScenarioRuntime()
    runtime = SkillEngineRuntime(core, registry=registry)

    result = runtime.run("browser.wikipedia.observe")

    assert result.success is False
    assert result.error == DAEMON_NOT_RUNNING


def test_skill_runtime_rejects_non_string_fill_selector(tmp_path):
    class DictSelectorScenarioRuntime(FakeScenarioRuntime):
        def run_step(self, step):
            self.steps.append(step)
            if step.action == "ui.locate":
                return {
                    "step_id": step.id,
                    "action": step.action,
                    "success": True,
                    "payload": step.payload,
                    "output": {
                        "best_match": {
                            "selector": {"type": "text", "value": {"text": "Search"}},
                            "role": "textbox",
                        },
                        "matches": [],
                    },
                    "validation": {"success": True, "errors": []},
                }
            return super().run_step(step)

    registry = SkillRegistry(default_root=tmp_path)
    skill = SkillLoader().load_file(
        Path("F:/AI_WORKSPACE/skills/browser/wikipedia.search.yaml")
    )
    registry.register(skill)
    core = FakeCore()
    core.scenario_runtime = DictSelectorScenarioRuntime()
    runtime = SkillEngineRuntime(core, registry=registry)

    result = runtime.run("browser.wikipedia.search", {"query": "AEGIS"})

    assert result.success is False
    assert (
        result.error
        == "browser.fill requires payload.selector to be a non-empty string CSS selector; got dict"
    )


def test_skill_runtime_recovers_browser_selector_once(tmp_path):
    class RecoveringScenarioRuntime:
        def __init__(self):
            self.steps = []
            self.fill_calls = 0

        def run_step(self, step):
            self.steps.append(step)
            if step.action == "ui.locate":
                return {
                    "step_id": step.id,
                    "action": step.action,
                    "success": True,
                    "payload": step.payload,
                    "output": {"best_match": {"selector": "#searchInput"}},
                    "validation": {"success": True, "errors": []},
                }
            if step.action == "browser.fill":
                self.fill_calls += 1
                if self.fill_calls == 1:
                    raise RuntimeError("element not found: #missing")
                return {
                    "step_id": step.id,
                    "action": step.action,
                    "success": True,
                    "payload": step.payload,
                    "output": {"success": True, **step.payload},
                    "validation": {"success": True, "errors": []},
                }
            raise AssertionError(step.action)

    registry = SkillRegistry(default_root=tmp_path)
    registry.register(
        Skill(
            id="test.recover.fill",
            name="Recover Fill",
            nodes=[
                SkillNode(
                    id="fill",
                    type="action",
                    action="browser.fill",
                    payload={"selector": "#missing", "value": "AEGIS"},
                    metadata={"query": "Search", "role": "textbox"},
                )
            ],
        )
    )
    core = FakeCore()
    core.scenario_runtime = RecoveringScenarioRuntime()
    core.recovery_engine = RecoveryEngineRuntime(
        core,
        history_path=tmp_path / "history.json",
    )
    runtime = SkillEngineRuntime(core, registry=registry)

    result = runtime.run("test.recover.fill")

    assert result.success is True
    assert core.scenario_runtime.fill_calls == 2
    assert result.node_results[0]["payload"]["selector"] == "#missing"
    assert result.node_results[0]["output"]["selector"] == "#searchInput"
    recovery = result.node_results[0]["metadata"]["recovery"]
    assert recovery["strategy"] == "browser_relocate"
    assert recovery["retry_success"] is True
    assert result.metadata["recovery"][0]["node_id"] == "fill"
    assert len(core.recovery_engine.history()) == 1


def test_skill_runtime_limits_recovery_to_one_retry(tmp_path):
    class AlwaysFailingScenarioRuntime:
        def __init__(self):
            self.steps = []

        def run_step(self, step):
            self.steps.append(step)
            if step.action == "ui.locate":
                return {
                    "step_id": step.id,
                    "action": step.action,
                    "success": True,
                    "payload": step.payload,
                    "output": {"best_match": {"selector": "#retry"}},
                    "validation": {"success": True, "errors": []},
                }
            raise RuntimeError("element not found")

    registry = SkillRegistry(default_root=tmp_path)
    registry.register(
        Skill(
            id="test.recover.once",
            name="Recover Once",
            nodes=[
                SkillNode(
                    id="fill",
                    type="action",
                    action="browser.fill",
                    payload={"selector": "#missing", "value": "AEGIS"},
                    metadata={"query": "Search"},
                )
            ],
        )
    )
    core = FakeCore()
    core.scenario_runtime = AlwaysFailingScenarioRuntime()
    core.recovery_engine = RecoveryEngineRuntime(
        core,
        history_path=tmp_path / "history.json",
    )
    runtime = SkillEngineRuntime(core, registry=registry)

    result = runtime.run("test.recover.once")

    assert result.success is False
    assert [step.action for step in core.scenario_runtime.steps] == [
        "browser.fill",
        "ui.locate",
        "browser.fill",
    ]
    recovery = result.node_results[0]["metadata"]["recovery"]
    assert recovery["retry_success"] is False
    assert len(core.recovery_engine.history()) == 1
