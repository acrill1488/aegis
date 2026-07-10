"""Persistent storage for Workflow Library catalogs."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import WorkflowTemplate

IMAGE_GENERATION_ROOT = Path(r"F:\AI_WORKSPACE\image_generation")
WORKFLOWS_ROOT = IMAGE_GENERATION_ROOT / "workflows"
WORKFLOW_CATALOG_PATH = WORKFLOWS_ROOT / "catalog.json"
AEGIS_WORKFLOWS_DIR = WORKFLOWS_ROOT / "aegis"
EXTERNAL_WORKFLOWS_DIR = WORKFLOWS_ROOT / "external"


class WorkflowLibraryStore:
    """JSON-backed workflow template catalog."""

    def __init__(self, catalog_path: Path | str = WORKFLOW_CATALOG_PATH):
        self.catalog_path = Path(catalog_path)
        self.ensure_layout()

    def ensure_layout(self) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        AEGIS_WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
        EXTERNAL_WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
        if not self.catalog_path.exists():
            self.save([])

    def load(self) -> list[WorkflowTemplate]:
        if not self.catalog_path.exists():
            return []
        data = json.loads(self.catalog_path.read_text(encoding="utf-8-sig") or "[]")
        if isinstance(data, dict):
            items = data.get("workflows", [])
        else:
            items = data
        return [self._template_from_dict(item) for item in items if isinstance(item, dict)]

    def save(self, templates: list[WorkflowTemplate]) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "workflows": [asdict(template) for template in sorted(templates, key=lambda item: item.id)],
        }
        self.catalog_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert(self, template: WorkflowTemplate) -> WorkflowTemplate:
        templates = {item.id: item for item in self.load()}
        templates[template.id] = template
        self.save(list(templates.values()))
        return template

    def _template_from_dict(self, data: dict[str, Any]) -> WorkflowTemplate:
        return WorkflowTemplate(
            id=str(data.get("id", "")),
            name=str(data.get("name") or data.get("id") or "Unnamed workflow"),
            path=str(data.get("path", "")),
            category=str(data.get("category", "general")),
            task_type=str(data.get("task_type", "txt2img")),
            model_family=str(data.get("model_family", "")),
            required_models=[str(item) for item in data.get("required_models", [])],
            supported_inputs=[str(item) for item in data.get("supported_inputs", ["prompt"])],
            default_width=int(data.get("default_width", 1024) or 1024),
            default_height=int(data.get("default_height", 1024) or 1024),
            metadata=dict(data.get("metadata") or {}),
        )
