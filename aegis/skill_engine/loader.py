from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import Skill, SkillNode


class SkillLoader:
    """Loads YAML skill graph definitions from files or directories."""

    def load_file(self, path: str | Path) -> Skill:
        skill_path = Path(path)
        with skill_path.open("r", encoding="utf-8-sig") as handle:
            raw = yaml.safe_load(handle) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Skill YAML must be an object: {skill_path}")
        return self._skill_from_dict(raw, source=str(skill_path))

    def load_dir(self, root: str | Path) -> list[Skill]:
        root_path = Path(root)
        if not root_path.exists():
            return []
        skills: list[Skill] = []
        for path in sorted(root_path.rglob("*.yaml")):
            skills.append(self.load_file(path))
        for path in sorted(root_path.rglob("*.yml")):
            skills.append(self.load_file(path))
        return skills

    def _skill_from_dict(self, raw: dict[str, Any], source: str) -> Skill:
        skill_id = str(raw.get("id") or "").strip()
        if not skill_id:
            raise ValueError(f"Skill id is required: {source}")

        node_items = raw.get("nodes", raw.get("steps", [])) or []
        if not isinstance(node_items, list):
            raise ValueError(f"Skill nodes/steps must be a list: {skill_id}")

        nodes = [
            self._node_from_item(item, index=index + 1, skill_id=skill_id)
            for index, item in enumerate(node_items)
        ]
        return Skill(
            id=skill_id,
            name=str(raw.get("name") or skill_id),
            version=str(raw.get("version") or "1"),
            description=str(raw.get("description") or ""),
            inputs=self._normalize_inputs(raw.get("inputs", raw.get("input", {}))),
            outputs=dict(raw.get("outputs") or {}),
            nodes=nodes,
            edges=self._normalize_edges(raw.get("edges") or []),
            metadata=dict(raw.get("metadata") or {}),
        )

    def _node_from_item(self, item: Any, *, index: int, skill_id: str) -> SkillNode:
        if isinstance(item, str):
            item = self._parse_step_string(item)
        if not isinstance(item, dict):
            raise ValueError(f"Skill node #{index} must be an object: {skill_id}")

        action = str(item.get("action") or "").strip()
        if not action:
            raise ValueError(f"Skill node #{index} action is required: {skill_id}")
        node_id = str(item.get("id") or self._default_node_id(action, index))
        node_type = str(item.get("type") or action.split(".", 1)[0])
        payload = item.get("payload", {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError(f"Skill node payload must be an object: {node_id}")
        return SkillNode(
            id=node_id,
            type=node_type,
            action=action,
            payload=payload,
            expect=dict(item.get("expect") or {}),
            retry=dict(item.get("retry") or {}),
            fallback=list(item.get("fallback") or []),
            metadata=dict(item.get("metadata") or {}),
        )

    def _parse_step_string(self, step: str) -> dict[str, Any]:
        action, _, argument = step.strip().partition(" ")
        payload: dict[str, Any] = {}
        argument = argument.strip()
        if argument:
            if action in {"browser.open", "browser.navigate"}:
                payload["url"] = argument
            elif action == "browser.press":
                payload["key"] = argument
            elif action == "ui.locate":
                payload["query"] = argument
            else:
                payload["value"] = argument
        return {"action": action, "payload": payload}

    def _default_node_id(self, action: str, index: int) -> str:
        safe_action = action.replace(".", "-").replace("_", "-")
        return f"{safe_action}-{index}"

    def _normalize_inputs(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, str):
            return {raw: {}}
        if isinstance(raw, list):
            return {str(item): {} for item in raw}
        if isinstance(raw, dict):
            return dict(raw)
        raise ValueError("Skill inputs/input must be an object, list, or string")

    def _normalize_edges(self, raw: Any) -> list[list[str]]:
        if not isinstance(raw, list):
            raise ValueError("Skill edges must be a list")
        edges: list[list[str]] = []
        for edge in raw:
            if not isinstance(edge, list) or len(edge) != 2:
                raise ValueError("Each skill edge must be a two-item list")
            edges.append([str(edge[0]), str(edge[1])])
        return edges
