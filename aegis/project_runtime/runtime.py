from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from aegis.serialization import to_plain

from .models import Project, ProjectArtifact
from .registry import DEFAULT_PROJECT_ROOT, ProjectRegistry

DEFAULT_LEGACY_MISSION_ROOT = Path(r"F:\AI_WORKSPACE\missions")


class ProjectRuntime:
    """Top-level runtime for Projects above missions and artifacts."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        registry: ProjectRegistry | None = None,
        root: str | Path = DEFAULT_PROJECT_ROOT,
        legacy_mission_root: str | Path = DEFAULT_LEGACY_MISSION_ROOT,
    ):
        self.core = core
        self.registry = registry or ProjectRegistry(root)
        self.active_path = self.registry.root / "active_project.json"
        self.legacy_mission_root = Path(legacy_mission_root)

    def create(self, name: str, description: str = "") -> Project:
        project = Project(
            id=self._new_id(),
            name=name,
            description=description,
        )
        project.workspace_path = str(self.registry.ensure_workspace(project.id))
        return self._with_activity(self.registry.save(project))

    def list(self) -> list[Project]:
        active_id = self._active_project_id()
        return [self._with_activity(project, active_id=active_id) for project in self.registry.list()]

    def get(self, project_id: str) -> Project | None:
        project = self.registry.get(project_id)
        if project is None:
            return None
        return self._with_activity(project)

    def show(self, project_id: str) -> Project:
        project = self.get(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        return project

    def set_active(self, project_id: str) -> Project:
        project = self.registry.get(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        self._write_active_project_id(project.id)
        return self._with_activity(project, active_id=project.id)

    def get_active(self) -> Project | None:
        project_id = self._active_project_id()
        if project_id is None:
            return None
        project = self.registry.get(project_id)
        if project is None:
            return None
        return self._with_activity(project, active_id=project_id)

    def add_mission(self, project_id: str, mission_id: str) -> Project:
        project = self.show(project_id)
        if mission_id not in project.mission_ids:
            project.mission_ids.append(mission_id)
        return self.registry.save(project)

    def add_artifact(self, project_id: str, type: str, path: str) -> ProjectArtifact:
        self.show(project_id)
        artifact = ProjectArtifact(
            id=self._new_artifact_id(),
            project_id=project_id,
            type=type,
            path=path,
        )
        return self.registry.save_artifact(artifact)

    def status(self, project_id: str) -> dict[str, Any]:
        missions = self.missions(project_id)
        project = self.show(project_id)
        artifacts = self.registry.list_artifacts(project.id)
        reports = self.reports(project.id)
        return {
            "id": project.id,
            "name": project.name,
            "status": project.status,
            "workspace_path": project.workspace_path,
            "mission_count": len(missions),
            "artifact_count": len(artifacts),
            "report_count": len(reports),
            "mission_ids": list(project.mission_ids),
            "updated_at": project.updated_at,
        }

    def details(self, project_id: str) -> dict[str, Any]:
        missions = self.missions(project_id)
        project = self.show(project_id)
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "workspace_path": project.workspace_path,
            "missions": missions,
            "artifacts": self.artifacts(project.id),
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }

    def missions(self, project_id: str) -> list[dict[str, Any]]:
        self._adopt_legacy_missions(project_id)
        project = self.show(project_id)
        workspace = Path(project.workspace_path) / "missions"
        missions: dict[str, dict[str, Any]] = {}
        for mission_id in project.mission_ids:
            missions[mission_id] = {"id": mission_id}
        for path in sorted(workspace.glob("mission_*/mission.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and data.get("id"):
                missions[str(data["id"])] = data
        for path in sorted(self.legacy_mission_root.glob("mission_*/mission.json")):
            data = self._read_json(path)
            if not isinstance(data, dict):
                continue
            mission_id = data.get("id")
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            if mission_id and metadata.get("project_id") == project.id:
                missions[str(mission_id)] = data
        return [missions[key] for key in sorted(missions)]

    def artifacts(self, project_id: str) -> list[ProjectArtifact]:
        self.show(project_id)
        return self.registry.list_artifacts(project_id)

    def reports(self, project_id: str) -> list[dict[str, Any]]:
        project = self.show(project_id)
        report_paths: list[tuple[str | None, Path]] = []
        workspace = Path(project.workspace_path)
        report_paths.extend((None, path) for path in sorted((workspace / "reports").glob("*.md")))
        for mission in self.missions(project.id):
            mission_id = str(mission.get("id") or "")
            mission_workspace = mission.get("workspace_path")
            if not mission_id or not mission_workspace:
                continue
            report_paths.append((mission_id, Path(str(mission_workspace)) / "report.md"))
        return [
            {
                "project_id": project.id,
                "mission_id": mission_id or self._mission_id_from_report(path),
                "path": str(path),
            }
            for mission_id, path in report_paths
            if path.exists()
        ]

    def _adopt_legacy_missions(self, project_id: str) -> None:
        project = self.show(project_id)
        active_id = self._active_project_id()
        if active_id != project.id or not self.legacy_mission_root.exists():
            return

        changed = False
        for path in sorted(self.legacy_mission_root.glob("mission_*/mission.json")):
            mission = self._read_json(path)
            if not isinstance(mission, dict) or not mission.get("id"):
                continue
            metadata = mission.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                mission["metadata"] = metadata
            existing_project_id = metadata.get("project_id")
            if existing_project_id and existing_project_id != project.id:
                continue

            mission_id = str(mission["id"])
            if existing_project_id != project.id:
                metadata["project_id"] = project.id
                path.write_text(
                    json.dumps(to_plain(mission), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            if mission_id not in project.mission_ids:
                project.mission_ids.append(mission_id)
                changed = True

        if changed:
            self.registry.save(project)

    def _read_json(self, path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def mission_workspace(self, project_id: str, mission_id: str) -> Path:
        project = self.show(project_id)
        workspace = Path(project.workspace_path) / "missions" / mission_id
        for child in ("logs", "outputs", "screenshots", "downloads"):
            (workspace / child).mkdir(parents=True, exist_ok=True)
        return workspace

    def _new_id(self) -> str:
        return f"project_{uuid4().hex}"

    def _new_artifact_id(self) -> str:
        return f"artifact_{uuid4().hex}"

    def _active_project_id(self) -> str | None:
        if not self.active_path.exists():
            return self._migrate_legacy_active_project()
        try:
            data = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if isinstance(data, dict):
            project_id = data.get("project_id")
            return str(project_id) if project_id else None
        if isinstance(data, str):
            return data
        return None

    def _migrate_legacy_active_project(self) -> str | None:
        for project_id in self._legacy_active_project_ids():
            project = self.registry.get(project_id)
            if project is None:
                continue
            self._write_active_project_id(project.id)
            self.registry.save(project)
            return project.id
        return None

    def _legacy_active_project_ids(self) -> list[str]:
        if not self.registry.index_path.exists():
            return []
        try:
            data = json.loads(self.registry.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        raw_projects = data.get("projects", []) if isinstance(data, dict) else []
        project_ids = []
        for raw_project in raw_projects:
            if not isinstance(raw_project, dict):
                continue
            if raw_project.get("status") == "active" and raw_project.get("id"):
                project_ids.append(str(raw_project["id"]))
        return project_ids

    def _write_active_project_id(self, project_id: str) -> None:
        self.active_path.parent.mkdir(parents=True, exist_ok=True)
        self.active_path.write_text(
            json.dumps({"project_id": project_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _with_activity(self, project: Project, *, active_id: str | None = None) -> Project:
        if active_id is None:
            active_id = self._active_project_id()
        project.status = "active" if active_id == project.id else "inactive"
        return project

    def _mission_id_from_report(self, path: Path) -> str | None:
        parent = path.parent
        if parent.name.startswith("mission_"):
            return parent.name
        return None

    def to_plain(self, value: Any) -> Any:
        return to_plain(value)
