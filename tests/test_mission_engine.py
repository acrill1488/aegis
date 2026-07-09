from __future__ import annotations

from aegis.goal_engine import Goal, GoalEngineRuntime
from aegis.mission_engine import MissionRuntime
from aegis.mission_engine.registry import MissionRegistry
from aegis.skill_engine import Skill, SkillRegistry


class FakeSkillResult:
    success = True
    error = None
    output = {"ok": True}


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
    assert skill_engine.calls == [("browser.wikipedia.search", {"query": "AEGIS"})]
