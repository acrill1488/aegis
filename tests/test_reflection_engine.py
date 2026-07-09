from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from aegis.operational_memory import OperationalMemoryRuntime
from aegis.recovery_engine import RecoveryEngineRuntime
from aegis.reflection_engine import ReflectionEngineRuntime, ReflectionStore


class CoreStub:
    pass


class MissionRuntimeStub:
    def __init__(self):
        self.missions = {}

    def save(self, mission):
        self.missions[mission.id] = mission
        return mission

    def show(self, mission_id):
        mission = self.missions.get(mission_id)
        if mission is None:
            raise KeyError(f"Mission not found: {mission_id}")
        return mission

    def list(self):
        return list(self.missions.values())


def make_runtime(tmp_path):
    core = CoreStub()
    core.operational_memory = OperationalMemoryRuntime(
        store_path=tmp_path / "operational_memory.json"
    )
    core.recovery_engine = RecoveryEngineRuntime(
        core,
        history_path=tmp_path / "recovery_history.json",
    )
    core.mission_runtime = MissionRuntimeStub()
    runtime = ReflectionEngineRuntime(
        core,
        store=ReflectionStore(
            tmp_path / "reflection" / "reports.json",
            tmp_path / "reflection" / "recommendations.json",
        ),
    )
    return core, runtime


def test_reflection_analyzes_failed_mission_and_records_memory(tmp_path):
    core, runtime = make_runtime(tmp_path)
    started_at = datetime.now(timezone.utc) - timedelta(seconds=90)
    completed_at = datetime.now(timezone.utc)
    mission = SimpleNamespace(
        id="mission_reflect_failed",
        goal="Exercise reflection",
        status="failed",
        created_at=started_at,
        started_at=started_at,
        completed_at=completed_at,
        workspace_path=str(tmp_path / "missions" / "mission_reflect_failed"),
        graph=[
            SimpleNamespace(
                id="node_1",
                skill_id="skill.unstable",
                status="failed",
                metadata={
                    "recovery": [
                        {
                            "strategy": "browser_relocate",
                            "retry_success": True,
                        },
                        {
                            "strategy": "browser_wait_reload",
                            "retry_success": False,
                        },
                    ],
                    "error": "boom",
                },
            )
        ],
        metadata={"project_id": "project_1"},
    )
    core.mission_runtime.save(mission)
    core.recovery_engine.record_attempt(
        source="skill:node_1",
        error="element not found",
        strategy="browser_relocate",
        success=True,
        metadata={"node_id": "node_1"},
    )
    for _ in range(2):
        core.operational_memory.record(
            {
                "type": "skill.failure",
                "source": "skill.unstable",
                "summary": "Skill unstable failed",
            }
        )
    core.operational_memory.record(
        {
            "type": "recovery.selector_patch",
            "source": "browser.fill",
            "summary": "Recovered selector",
            "data": {"old_selector": "#old", "new_selector": "#new"},
        }
    )

    report = runtime.analyze_mission(mission.id)

    recommendation_types = {item.type for item in report.recommendations}
    assert report.mission_id == mission.id
    assert report.project_id == "project_1"
    assert report.success is False
    assert report.duration is not None and report.duration > 60
    assert report.recovery_count == 3
    assert {
        "mission_failure",
        "recovery_used",
        "skill_unstable",
        "performance",
        "selector_update",
        "skill_review",
    }.issubset(recommendation_types)
    assert runtime.latest().id == report.id
    assert runtime.stats()["report_count"] == 1
    assert core.operational_memory.list(type="reflection.report")[0].data[
        "report_id"
    ] == report.id


def test_reflection_analyzes_latest_completed_or_failed_mission(tmp_path):
    core, runtime = make_runtime(tmp_path)
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    new_time = datetime.now(timezone.utc)
    core.mission_runtime.save(
        SimpleNamespace(
            id="mission_old",
            goal="Old",
            status="completed",
            created_at=old_time,
            started_at=old_time,
            completed_at=old_time,
            workspace_path=str(tmp_path / "missions" / "mission_old"),
            graph=[],
            metadata={},
        )
    )
    core.mission_runtime.save(
        SimpleNamespace(
            id="mission_new",
            goal="New",
            status="completed",
            created_at=new_time,
            started_at=new_time,
            completed_at=new_time,
            workspace_path=str(tmp_path / "missions" / "mission_new"),
            graph=[],
            metadata={},
        )
    )

    report = runtime.analyze_mission()

    assert report.mission_id == "mission_new"
    assert report.summary.startswith("Mission mission_new succeeded")
