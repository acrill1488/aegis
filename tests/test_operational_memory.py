from aegis.operational_memory import OperationalMemoryRuntime
from aegis.recovery_engine import RecoveryEngineRuntime
from aegis.skill_engine import Skill, SkillEngineRuntime, SkillNode, SkillRegistry


def test_operational_memory_records_filters_and_clears(tmp_path):
    runtime = OperationalMemoryRuntime(store_path=tmp_path / "operational_memory.json")

    runtime.record(
        {
            "type": "skill.success",
            "source": "skill.one",
            "summary": "Skill one succeeded",
            "data": {"skill_id": "skill.one"},
        }
    )
    runtime.record(
        {
            "type": "mission.failure",
            "source": "mission_1",
            "summary": "Mission failed",
            "data": {"mission_id": "mission_1", "error": "boom"},
        }
    )

    assert runtime.stats()["total"] == 2
    assert runtime.list(type="skill.success")[0].source == "skill.one"
    assert runtime.search("boom")[0].type == "mission.failure"
    assert runtime.clear(type="skill.success") == 1
    assert runtime.stats()["total"] == 1


def test_operational_memory_suggests_latest_recovered_selector(tmp_path):
    runtime = OperationalMemoryRuntime(store_path=tmp_path / "operational_memory.json")
    runtime.record(
        {
            "type": "recovery.selector_patch",
            "source": "browser.fill",
            "summary": "Recovered selector for browser.fill",
            "data": {
                "old_selector": "#missing",
                "new_selector": "#search",
                "query": "Search",
                "role": "textbox",
                "error": "element not found",
                "strategy": "browser_relocate",
            },
        }
    )

    assert (
        runtime.suggest_selector("browser.fill", "Search", role="textbox")
        == "#search"
    )
    assert runtime.suggest_selector("browser.click", "Search", role="textbox") is None


def test_skill_recovery_records_operational_selector_patch(tmp_path):
    class RecoveringScenarioRuntime:
        def __init__(self):
            self.fill_calls = 0

        def run_step(self, step):
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

    class Core:
        def __init__(self):
            self.scenario_runtime = RecoveringScenarioRuntime()
            self.operational_memory = OperationalMemoryRuntime(
                store_path=tmp_path / "operational_memory.json"
            )
            self.recovery_engine = RecoveryEngineRuntime(
                self,
                history_path=tmp_path / "history.json",
            )

    registry = SkillRegistry(default_root=tmp_path / "missing")
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
    core = Core()
    result = SkillEngineRuntime(core, registry=registry).run("test.recover.fill")

    assert result.success is True
    assert core.operational_memory.suggest_selector(
        "browser.fill",
        "Search",
        role="textbox",
    ) == "#searchInput"
    assert core.operational_memory.list(type="skill.success")[0].source == (
        "test.recover.fill"
    )
