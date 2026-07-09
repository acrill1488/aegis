from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import Project, ProjectArtifact


DEFAULT_PROJECT_ROOT = Path(r"F:\AI_WORKSPACE\projects")


class ProjectRegistry:
    """File-backed registry for long-lived Project containers."""

    def __init__(self, root: str | Path = DEFAULT_PROJECT_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "projects.json"

    def save(self, project: Project) -> Project:
        workspace = Path(project.workspace_path) if project.workspace_path else self.workspace_path(project.id)
        project.workspace_path = str(workspace)
        project.updated_at = self._now()
        self.ensure_workspace(project.id)
        self._write_json(workspace / "project.json", self._project_to_plain(project))
        projects = {item.id: item for item in self.list()}
        projects[project.id] = project
        self._write_json(
            self.index_path,
            {"projects": [self._project_to_plain(item) for item in projects.values()]},
        )
        return project

    def get(self, project_id: str) -> Project | None:
        projects = {project.id: project for project in self.list()}
        project = projects.get(project_id)
        if project is not None:
            return project

        path = self.workspace_path(project_id) / "project.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        try:
            return self._project_from_plain(data)
        except (KeyError, TypeError, ValueError):
            return None

    def list(self) -> list[Project]:
        projects: dict[str, Project] = {}
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            raw_projects = data.get("projects", []) if isinstance(data, dict) else []
            for raw_project in raw_projects:
                if not isinstance(raw_project, dict):
                    continue
                try:
                    project = self._project_from_plain(raw_project)
                except (KeyError, TypeError, ValueError):
                    continue
                projects[project.id] = project

        for path in sorted(self.root.glob("project_*/project.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                project = self._project_from_plain(data)
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            projects[project.id] = project
        return [projects[key] for key in sorted(projects)]

    def workspace_path(self, project_id: str) -> Path:
        return self.root / project_id

    def ensure_workspace(self, project_id: str) -> Path:
        workspace = self.workspace_path(project_id)
        for child in ("missions", "artifacts", "reports", "memory", "knowledge"):
            (workspace / child).mkdir(parents=True, exist_ok=True)
        return workspace

    def save_artifact(self, artifact: ProjectArtifact) -> ProjectArtifact:
        project = self.get(artifact.project_id)
        if project is None:
            raise KeyError(f"Project not found: {artifact.project_id}")
        artifacts_path = self.workspace_path(project.id) / "artifacts" / "artifacts.json"
        artifacts = self.list_artifacts(project.id)
        artifacts = [item for item in artifacts if item.id != artifact.id]
        artifacts.append(artifact)
        self._write_json(artifacts_path, {"artifacts": artifacts})
        return artifact

    def list_artifacts(self, project_id: str) -> list[ProjectArtifact]:
        artifacts_path = self.workspace_path(project_id) / "artifacts" / "artifacts.json"
        if not artifacts_path.exists():
            return []
        try:
            data = json.loads(artifacts_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        raw_artifacts = data.get("artifacts", []) if isinstance(data, dict) else []
        artifacts = []
        for raw_artifact in raw_artifacts:
            if not isinstance(raw_artifact, dict):
                continue
            try:
                artifacts.append(self._artifact_from_plain(raw_artifact))
            except (KeyError, TypeError, ValueError):
                continue
        return artifacts

    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(to_plain(value), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _project_from_plain(self, data: dict[str, Any]) -> Project:
        mission_ids = data.get("mission_ids") or []
        if not isinstance(mission_ids, list):
            mission_ids = []
        project_id = str(data["id"])
        return Project(
            id=project_id,
            name=str(data["name"]),
            description=str(data.get("description", "")),
            status=str(data.get("status", "inactive")),
            created_at=self._datetime(data.get("created_at")),
            updated_at=self._datetime(data.get("updated_at")),
            workspace_path=str(data.get("workspace_path") or self.workspace_path(project_id)),
            mission_ids=[str(mission_id) for mission_id in mission_ids],
            metadata=dict(data.get("metadata") or {}),
        )

    def _artifact_from_plain(self, data: dict[str, Any]) -> ProjectArtifact:
        return ProjectArtifact(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            type=str(data["type"]),
            path=str(data["path"]),
            created_at=self._datetime(data.get("created_at")),
            metadata=dict(data.get("metadata") or {}),
        )

    def _project_to_plain(self, project: Project) -> dict[str, Any]:
        data = to_plain(project)
        if isinstance(data, dict):
            data.pop("status", None)
        return data

    def _datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return self._now()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
