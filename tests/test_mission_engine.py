from __future__ import annotations

from aegis.goal_engine import Goal, GoalEngineRuntime
from aegis.mission_engine import MissionNode, MissionRuntime
from aegis.mission_engine.registry import MissionRegistry
from aegis.skill_engine import Skill, SkillRegistry


class FakeSkillResult:
    success = True
    error = None
    output = {"ok": True}
    metadata = {}


class FakeSkillEngine:
    def __init__(self, registry):
        self.skills = registry
        self.calls = []

    def run(self, skill_id, inputs):
        self.calls.append((skill_id, inputs))
        return FakeSkillResult()


def test_mission_runtime_creates_workspace_and_report(tmp_path):
    registry = SkillRegistry(default_root=tmp_path / "missing")
    registry.register(Skill(id="browser.wikipedia.search", name="Wikipedia Search"))
    skill_engine = FakeSkillEngine(registry)
    runtime = MissionRuntime(
        skill_engine=skill_engine,
        registry=MissionRegistry(tmp_path / "missions"),
    )
    goal = Goal(
        id="goal_1",
        text="Wikipedia AEGIS",
        intent="search.wikipedia",
        confidence=0.9,
        selected_skill="browser.wikipedia.search",
        inputs={"query": "AEGIS"},
    )

    mission = runtime.create(goal)
    result = runtime.run(mission.id)
    completed = runtime.show(mission.id)

    assert result.success is True
    assert completed.status == "completed"
    assert completed.graph[0].status == "completed"
    assert skill_engine.calls == [("browser.wikipedia.search", {"query": "AEGIS"})]
    assert (tmp_path / "missions" / mission.id / "mission.json").exists()
    assert (tmp_path / "missions" / mission.id / "goal.json").exists()
    assert (tmp_path / "missions" / mission.id / "graph.json").exists()
    report = tmp_path / "missions" / mission.id / "report.md"
    assert report.exists()
    assert "## Goal" in report.read_text(encoding="utf-8")


def test_goal_runtime_executes_through_mission_runtime(tmp_path):
    registry = SkillRegistry(default_root=tmp_path / "missing")
    registry.register(Skill(id="browser.wikipedia.search", name="Wikipedia Search"))
    skill_engine = FakeSkillEngine(registry)
    mission_runtime = MissionRuntime(
        skill_engine=skill_engine,
        registry=MissionRegistry(tmp_path / "missions"),
    )
    runtime = GoalEngineRuntime(
        skill_engine=skill_engine,
        mission_runtime=mission_runtime,
    )

    execution = runtime.execute("Wikipedia AEGIS")

    assert execution["success"] is True
    assert execution["mission"].status == "completed"
    assert execution["mission_result"].success is True
    assert execution["result"] is execution["mission_result"]
    assert skill_engine.calls == [("browser.wikipedia.search", {"query": "AEGIS"})]


def test_mission_runtime_passes_event_context_to_skill_engine(tmp_path):
    class ContextSkillEngine(FakeSkillEngine):
        def __init__(self, registry):
            super().__init__(registry)
            self.contexts = []

        def run(self, skill_id, inputs, context=None):
            self.contexts.append(context)
            return super().run(skill_id, inputs)

    registry = SkillRegistry(default_root=tmp_path / "missing")
    registry.register(Skill(id="browser.wikipedia.search", name="Wikipedia Search"))
    skill_engine = ContextSkillEngine(registry)
    runtime = MissionRuntime(
        skill_engine=skill_engine,
        registry=MissionRegistry(tmp_path / "missions"),
    )
    mission = runtime.create(
        "test mission",
        metadata={"project_id": "project_1"},
    )
    mission.graph = [
        MissionNode(
            id="node_1",
            skill_id="browser.wikipedia.search",
            inputs={"query": "AEGIS"},
        )
    ]
    runtime.registry.save(mission)

    runtime.run(mission.id)

    assert skill_engine.contexts == [
        {
            "project_id": "project_1",
            "mission_id": mission.id,
            "correlation_id": mission.metadata["correlation_id"],
        }
    ]


def test_mission_result_keeps_skill_recovery_info(tmp_path):
    class RecoverySkillResult:
        success = False
        error = "Skill execution failed"
        output = {}
        metadata = {
            "recovery": [
                {
                    "node_id": "fill",
                    "strategy": "browser_relocate",
                    "retry_success": False,
                }
            ]
        }

    class RecoverySkillEngine(FakeSkillEngine):
        def run(self, skill_id, inputs):
            self.calls.append((skill_id, inputs))
            return RecoverySkillResult()

    registry = SkillRegistry(default_root=tmp_path / "missing")
    registry.register(Skill(id="browser.wikipedia.search", name="Wikipedia Search"))
    skill_engine = RecoverySkillEngine(registry)
    runtime = MissionRuntime(
        skill_engine=skill_engine,
        registry=MissionRegistry(tmp_path / "missions"),
    )
    mission = runtime.create("test mission")
    mission.graph = [
        MissionNode(
            id="node_1",
            skill_id="browser.wikipedia.search",
            inputs={"query": "AEGIS"},
        )
    ]
    runtime.registry.save(mission)

    result = runtime.run(mission.id)

    assert result.success is False
    assert result.metadata["recovery"][0]["node_id"] == "node_1"
    assert (
        result.metadata["recovery"][0]["recovery"][0]["strategy"]
        == "browser_relocate"
    )
