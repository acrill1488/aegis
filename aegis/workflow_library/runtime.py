"""Workflow Library Runtime v1."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from aegis.image_generation.model_catalog import ImageModelCatalog
from aegis.serialization import to_plain

from .models import WorkflowTemplate, WorkflowValidationResult
from .store import WORKFLOWS_ROOT, WorkflowLibraryStore


class WorkflowLibraryRuntime:
    """Catalog and selection runtime for ComfyUI workflow templates."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        store: WorkflowLibraryStore | None = None,
        model_catalog: ImageModelCatalog | None = None,
    ):
        self.core = core
        self.store = store or WorkflowLibraryStore()
        self.model_catalog = model_catalog or ImageModelCatalog(core=core)

    def scan(self, root: str | Path | None = None) -> list[WorkflowTemplate]:
        scan_root = Path(root) if root is not None else WORKFLOWS_ROOT
        self.store.ensure_layout()
        templates = {template.id: template for template in self.store.load()}
        discovered = 0
        if scan_root.exists():
            for workflow_path in sorted(scan_root.rglob("*.json")):
                if workflow_path.name == "catalog.json" or workflow_path.name.endswith(".meta.json"):
                    continue
                template = self._template_from_workflow_path(workflow_path)
                templates[template.id] = template
                discovered += 1
        self.store.save(list(templates.values()))
        result = list(sorted(templates.values(), key=lambda item: item.id))
        self._publish(
            "workflow.scan.completed",
            {"root": str(scan_root), "discovered": discovered, "total": len(result)},
        )
        return result

    def list(
        self,
        category: str | None = None,
        task_type: str | None = None,
    ) -> list[WorkflowTemplate]:
        templates = self.store.load()
        if category:
            templates = [item for item in templates if item.category == category]
        if task_type:
            templates = [item for item in templates if item.task_type == task_type]
        return list(sorted(templates, key=lambda item: item.id))

    def get(self, workflow_id: str) -> WorkflowTemplate | None:
        return next((item for item in self.store.load() if item.id == workflow_id), None)

    def search(self, query: str) -> list[WorkflowTemplate]:
        needle = query.lower()
        return [
            item
            for item in self.store.load()
            if needle in self._search_text(item)
        ]

    def validate(self, workflow_id: str) -> WorkflowValidationResult:
        template = self.get(workflow_id)
        if template is None:
            result = WorkflowValidationResult(
                workflow_id=workflow_id,
                success=False,
                warnings=["Workflow not found"],
            )
            self._publish("workflow.validation.completed", {"result": result})
            return result

        warnings: list[str] = []
        path = Path(template.path)
        if not path.exists():
            warnings.append("Workflow file not found")
        installed_models = {model.id for model in self.model_catalog.list() if model.installed}
        installed_filenames = {
            Path(model.local_path).name.lower()
            for model in self.model_catalog.list()
            if model.installed and model.local_path
        }
        missing = [
            model
            for model in template.required_models
            if model not in installed_models and Path(model).name.lower() not in installed_filenames
        ]
        result = WorkflowValidationResult(
            workflow_id=workflow_id,
            success=not missing and not warnings,
            missing_models=missing,
            warnings=warnings,
            metadata={"path": template.path},
        )
        self._publish("workflow.validation.completed", {"result": result})
        return result

    def select(
        self,
        task_type: str,
        model_family: str | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowTemplate | None:
        candidates = [item for item in self.store.load() if item.task_type == task_type]
        if model_family:
            candidates = [item for item in candidates if item.model_family == model_family]
        if tags:
            required = {tag.lower() for tag in tags}
            candidates = [
                item
                for item in candidates
                if required.issubset({tag.lower() for tag in item.metadata.get("tags", [])})
            ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: (len(self.validate(item.id).missing_models), item.name.lower()))
        return candidates[0]

    def register(self, template: WorkflowTemplate) -> WorkflowTemplate:
        registered = self.store.upsert(template)
        self._publish("workflow.registered", {"workflow": registered})
        return registered

    def _template_from_workflow_path(self, workflow_path: Path) -> WorkflowTemplate:
        metadata = self._load_metadata(workflow_path)
        workflow_id = str(metadata.get("id") or self._slug(workflow_path.stem))
        return WorkflowTemplate(
            id=workflow_id,
            name=str(metadata.get("name") or workflow_path.stem.replace("_", " ").title()),
            path=str(workflow_path),
            category=str(metadata.get("category", "general")),
            task_type=str(metadata.get("task_type", "txt2img")),
            model_family=str(metadata.get("model_family", "")),
            required_models=[str(item) for item in metadata.get("required_models", [])],
            supported_inputs=[str(item) for item in metadata.get("supported_inputs", ["prompt"])],
            default_width=int(metadata.get("default_width", 1024) or 1024),
            default_height=int(metadata.get("default_height", 1024) or 1024),
            metadata={key: value for key, value in metadata.items() if key not in self._template_keys()},
        )

    def _load_metadata(self, workflow_path: Path) -> dict[str, Any]:
        candidates = [
            workflow_path.with_name(f"{workflow_path.stem}.meta.json"),
            workflow_path.with_name("default.meta.json"),
        ]
        for meta_path in candidates:
            if not meta_path.exists():
                continue
            data = json.loads(meta_path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
        return {}

    def _search_text(self, template: WorkflowTemplate) -> str:
        return " ".join(
            [
                template.id,
                template.name,
                template.category,
                template.task_type,
                template.model_family,
                " ".join(template.required_models),
                json.dumps(template.metadata, ensure_ascii=False),
            ]
        ).lower()

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "workflow"

    def _template_keys(self) -> set[str]:
        return {
            "id",
            "name",
            "path",
            "category",
            "task_type",
            "model_family",
            "required_models",
            "supported_inputs",
            "default_width",
            "default_height",
        }

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        events = getattr(self.core, "events", None)
        publish = getattr(events, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, source="workflow_library_runtime", payload=to_plain(payload))
        except Exception:
            return
