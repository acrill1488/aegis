from __future__ import annotations

import json

from aegis.goal_engine import Goal
from aegis.mission_engine import MissionRuntime
from aegis.mission_engine.registry import MissionRegistry
from aegis.project_runtime import ProjectRegistry, ProjectRuntime


class CoreStub:
    pass


def test_project_runtime_creates_workspace_and_active_project(tmp_path):
    runtime = ProjectRuntime(
        registry=ProjectRegistry(tmp_path / "projects"),
        legacy_mission_root=tmp_path / "missions",
    )

    project = runtime.create("AEGIS", description="Runtime container")
    active = runtime.set_active(project.id)

    assert active.id == project.id
    assert runtime.get_active().id == project.id
    assert (tmp_path / "projects" / "projects.json").exists()
    index = json.loads((tmp_path / "projects" / "projects.json").read_text(encoding="utf-8"))
    assert "status" not in index["projects"][0]
    assert runtime.list()[0].status == "active"
    assert (tmp_path / "projects" / project.id / "project.json").exists()
    for child in ("missions", "artifacts", "reports", "memory", "knowledge"):
        assert (tmp_path / "projects" / project.id / child).is_dir()


def test_project_runtime_migrates_legacy_active_status(tmp_path):
    runtime = ProjectRuntime(
        registry=ProjectRegistry(tmp_path / "projects"),
        legacy_mission_root=tmp_path / "missions",
    )
    project = runtime.create("AEGIS", description="Runtime container")
    index_path = tmp_path / "projects" / "projects.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["projects"][0]["status"] = "active"
    index_path.write_text(json.dumps(index), encoding="utf-8")

    migrated = ProjectRuntime(
        registry=ProjectRegistry(tmp_path / "projects"),
        legacy_mission_root=tmp_path / "missions",
    )
    active = migrated.get_active()

    assert active is not None
    assert active.id == project.id
    assert json.loads((tmp_path / "projects" / "active_project.json").read_text()) == {
        "project_id": project.id
    }
    cleaned_index = json.loads(index_path.read_text(encoding="utf-8"))
    assert "status" not in cleaned_index["projects"][0]


def test_active_project_receives_mission_metadata_and_workspace(tmp_path):
    core = CoreStub()
    core.project_runtime = ProjectRuntime(
        registry=ProjectRegistry(tmp_path / "projects"),
        legacy_mission_root=tmp_path / "missions",
    )
    project = core.project_runtime.create("AEGIS")
    core.project_runtime.set_active(project.id)
    runtime = MissionRuntime(
        core,
        registry=MissionRegistry(
            tmp_path / "missions",
            project_root=tmp_path / "projects",
        ),
    )
    goal = Goal(
        id="goal_1",
        text="Run project mission",
        intent="test",
        confidence=1.0,
        selected_skill="skill.test",
        inputs={},
    )

    mission = runtime.create(goal)
    updated_project = core.project_runtime.show(project.id)

    assert mission.metadata["project_id"] == project.id
    assert mission.id in updated_project.mission_ids
    assert mission.workspace_path == str(
        tmp_path / "projects" / project.id / "missions" / mission.id
    )
    assert core.project_runtime.missions(project.id)[0]["id"] == mission.id
    assert (tmp_path / "projects" / project.id / "missions" / mission.id / "mission.json").exists()
    stored_project = json.loads(
        (tmp_path / "projects" / project.id / "project.json").read_text(encoding="utf-8")
    )
    assert "status" not in stored_project
    assert not (tmp_path / "missions" / mission.id / "mission.json").exists()

    result = runtime.run(mission.id)

    assert result.report_path == str(
        tmp_path / "projects" / project.id / "missions" / mission.id / "report.md"
    )
    assert core.project_runtime.reports(project.id) == [
        {
            "project_id": project.id,
            "mission_id": mission.id,
            "path": result.report_path,
        }
    ]


def test_active_project_adopts_legacy_unassigned_missions(tmp_path):
    legacy_root = tmp_path / "legacy_missions"
    mission_dir = legacy_root / "mission_legacy"
    mission_dir.mkdir(parents=True)
    mission_path = mission_dir / "mission.json"
    report_path = mission_dir / "report.md"
    mission_path.write_text(
        json.dumps(
            {
                "id": "mission_legacy",
                "goal": "Legacy mission",
                "status": "completed",
                "workspace_path": str(mission_dir),
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text("# Legacy report", encoding="utf-8")
    runtime = ProjectRuntime(
        registry=ProjectRegistry(tmp_path / "projects"),
        legacy_mission_root=legacy_root,
    )
    project = runtime.create("AEGIS")
    runtime.set_active(project.id)

    missions = runtime.missions(project.id)

    assert missions[0]["id"] == "mission_legacy"
    assert missions[0]["metadata"]["project_id"] == project.id
    assert runtime.show(project.id).mission_ids == ["mission_legacy"]
    assert json.loads(mission_path.read_text(encoding="utf-8"))["metadata"]["project_id"] == project.id
    assert runtime.reports(project.id) == [
        {
            "project_id": project.id,
            "mission_id": "mission_legacy",
            "path": str(report_path),
        }
    ]
