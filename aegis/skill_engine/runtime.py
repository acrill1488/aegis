from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from aegis.serialization import to_plain
from aegis.scenarios import ScenarioRuntime, ScenarioStep

from .models import Skill, SkillNode, SkillRunResult
from .registry import SkillRegistry


class _RecoveredActionError(RuntimeError):
    def __init__(self, message: str, recovery_metadata: dict[str, Any]):
        super().__init__(message)
        self.recovery_metadata = recovery_metadata


class SkillEngineRuntime:
    """Executes reusable YAML skill graphs through AEGIS runtime boundaries."""

    _SUPPORTED_ACTIONS = {
        "browser.open",
        "browser.click",
        "browser.fill",
        "browser.press",
        "browser.wait",
        "browser.text",
        "browser.screenshot",
        "ui.observe",
        "ui.locate",
    }
    _VARIABLE_RE = re.compile(r"{{\s*([^{}]+?)\s*}}")

    def __init__(
        self,
        core: Any | None = None,
        *,
        registry: SkillRegistry | None = None,
    ):
        self.core = core
        self.skills = registry or SkillRegistry()
        self.skills.load_defaults()
        self.action_dispatcher = getattr(core, "scenario_runtime", None)
        if self.action_dispatcher is None:
            self.action_dispatcher = ScenarioRuntime(core)
        self.recovery_engine = getattr(core, "recovery_engine", None)

    def run(
        self,
        skill_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> SkillRunResult:
        return self._execute(skill_id, inputs=inputs, dry_run=False)

    def dry_run(
        self,
        skill_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> SkillRunResult:
        return self._execute(skill_id, inputs=inputs, dry_run=True)

    def validate(self, skill_id: str) -> dict[str, Any]:
        skill = self._get_skill(skill_id)
        errors: list[str] = []
        node_ids = set()

        for node in skill.nodes:
            if not node.id:
                errors.append("Node id is required")
            if node.id in node_ids:
                errors.append(f"Duplicate node id: {node.id}")
            node_ids.add(node.id)
            if node.action not in self._SUPPORTED_ACTIONS:
                errors.append(f"Unsupported action in node {node.id}: {node.action}")

        for edge in skill.edges:
            if len(edge) != 2:
                errors.append(f"Invalid edge: {edge}")
                continue
            source, target = edge
            if source not in node_ids:
                errors.append(f"Edge references missing source node: {source}")
            if target not in node_ids:
                errors.append(f"Edge references missing target node: {target}")

        return {
            "success": not errors,
            "skill_id": skill.id,
            "node_count": len(skill.nodes),
            "edge_count": len(skill.edges),
            "errors": errors,
        }

    def _execute(
        self,
        skill_id: str,
        *,
        inputs: dict[str, Any] | None,
        dry_run: bool,
    ) -> SkillRunResult:
        skill = self._get_skill(skill_id)
        validation = self.validate(skill_id)
        if not validation["success"]:
            raise ValueError("; ".join(validation["errors"]))

        started_at = self._now()
        context: dict[str, Any] = {"inputs": inputs or {}, "nodes": {}}
        node_results: list[dict[str, Any]] = []
        success = True
        error: str | None = None

        for node in skill.nodes:
            try:
                result = self._run_node(node, context=context, dry_run=dry_run)
            except Exception as exc:
                result = self._failed_node_result(
                    node,
                    exc,
                    recovery=getattr(exc, "recovery_metadata", None),
                )
            node_results.append(result)
            context["nodes"][node.id] = result
            if not result.get("success"):
                success = False
                error = result.get("error") or "; ".join(
                    result.get("validation", {}).get("errors", [])
                )
                break

        completed_at = self._now()
        output = self._build_output(skill, context, node_results)
        recovery = [
            {
                "node_id": result.get("node_id"),
                "action": result.get("action"),
                **dict(result.get("metadata", {}).get("recovery") or {}),
            }
            for result in node_results
            if result.get("metadata", {}).get("recovery")
        ]
        return SkillRunResult(
            skill_id=skill.id,
            success=success,
            started_at=started_at,
            completed_at=completed_at,
            node_results=node_results,
            output=output,
            error=error,
            metadata={
                "skill_name": skill.name,
                "dry_run": dry_run,
                "recovery": recovery,
            },
        )

    def _run_node(
        self,
        node: SkillNode,
        *,
        context: dict[str, Any],
        dry_run: bool,
    ) -> dict[str, Any]:
        started_at = self._now()
        payload = self._resolve_value(node.payload, context)
        expect = self._resolve_value(node.expect, context)
        if dry_run:
            output = {"dry_run": True, "action": node.action, "payload": payload}
            validation = {"success": True, "errors": [], "skipped": True}
        else:
            self._validate_action_payload(node.action, payload)
            output, recovery = self._invoke_action_with_recovery(
                node,
                payload,
                context=context,
            )
            validation = self.validate_expect(output, expect)
        completed_at = self._now()
        metadata = to_plain(node.metadata)
        if not dry_run and recovery:
            metadata["recovery"] = recovery
        return {
            "node_id": node.id,
            "type": node.type,
            "action": node.action,
            "success": validation["success"],
            "started_at": started_at,
            "completed_at": completed_at,
            "payload": to_plain(payload),
            "output": to_plain(output),
            "expect": to_plain(expect),
            "validation": validation,
            "metadata": metadata,
        }

    def _invoke_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        target_result = self.action_dispatcher.run_step(
            ScenarioStep(id="skill-node", action=action, payload=payload)
        )
        if not target_result.get("success"):
            raise RuntimeError(
                target_result.get("error")
                or "; ".join(target_result.get("validation", {}).get("errors", []))
            )
        return to_plain(target_result.get("output") or {})

    def _invoke_action_with_recovery(
        self,
        node: SkillNode,
        payload: dict[str, Any],
        *,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        try:
            return self._invoke_action(node.action, payload), None
        except Exception as exc:
            recovery_engine = self.recovery_engine
            if recovery_engine is None:
                raise
            decision = recovery_engine.recover(
                node.action,
                payload,
                exc,
                context={
                    "source": f"skill:{node.id}",
                    "metadata": node.metadata,
                    "action_dispatcher": self.action_dispatcher,
                    "attempt_metadata": {
                        "node_id": node.id,
                        "node_type": node.type,
                    },
                },
            )
            recovery_metadata = {
                "attempted": True,
                "strategy": decision.strategy,
                "should_retry": decision.should_retry,
                "reason": decision.reason,
                "patched_payload": to_plain(decision.patched_payload),
                "metadata": to_plain(decision.metadata),
                "original_error": str(exc),
            }
            if not decision.should_retry:
                raise _RecoveredActionError(str(exc), recovery_metadata) from exc
            try:
                output = self._invoke_action(node.action, decision.patched_payload)
            except Exception as retry_exc:
                recovery_metadata["retry_success"] = False
                recovery_metadata["retry_error"] = str(retry_exc)
                raise _RecoveredActionError(
                    str(retry_exc),
                    recovery_metadata,
                ) from exc
            recovery_metadata["retry_success"] = True
            return output, recovery_metadata

    def _validate_action_payload(self, action: str, payload: dict[str, Any]) -> None:
        if action not in {"browser.fill", "browser.click"}:
            return
        selector = payload.get("selector")
        if not isinstance(selector, str) or not selector.strip():
            actual_type = type(selector).__name__
            raise ValueError(
                f"{action} requires payload.selector to be a non-empty string "
                f"CSS selector; got {actual_type}"
            )

    def validate_expect(self, output: Any, expect: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        if not expect:
            return {"success": True, "errors": errors}

        if "contains_text" in expect:
            wanted = str(expect["contains_text"])
            if wanted.casefold() not in self._flatten_text(output).casefold():
                errors.append(f"Expected output to contain text: {wanted}")

        if "url_contains" in expect:
            wanted = str(expect["url_contains"])
            url = self._find_key(output, "url")
            if wanted.casefold() not in str(url or "").casefold():
                errors.append(f"Expected url to contain: {wanted}")

        if "title_contains" in expect:
            wanted = str(expect["title_contains"])
            title = self._find_key(output, "title")
            if wanted.casefold() not in str(title or "").casefold():
                errors.append(f"Expected title to contain: {wanted}")

        if "element_exists" in expect and bool(expect["element_exists"]):
            if not self._element_exists(output):
                errors.append("Expected an element to exist")

        if "success_true" in expect and bool(expect["success_true"]):
            success_value = self._find_key(output, "success")
            if success_value is not True:
                errors.append("Expected output.success to be true")

        return {"success": not errors, "errors": errors}

    def _resolve_value(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: self._resolve_value(item, context) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_value(item, context) for item in value]
        if not isinstance(value, str):
            return value

        match = self._VARIABLE_RE.fullmatch(value)
        if match:
            return self._lookup_variable(match.group(1), context)

        def replace(match: re.Match[str]) -> str:
            resolved = self._lookup_variable(match.group(1), context)
            return "" if resolved is None else str(resolved)

        return self._VARIABLE_RE.sub(replace, value)

    def _lookup_variable(self, expression: str, context: dict[str, Any]) -> Any:
        parts = [part.strip() for part in expression.split(".") if part.strip()]
        if not parts:
            return None
        if parts[0] == "inputs":
            return self._walk(context.get("inputs", {}), parts[1:])
        if parts[0] == "nodes" and len(parts) >= 2:
            node_result = context.get("nodes", {}).get(parts[1], {})
            if len(parts) >= 3 and parts[2] == "output":
                return self._walk(node_result.get("output", {}), parts[3:])
            return self._walk(node_result.get("output", {}), parts[2:])
        return self._walk(context, parts)

    def _walk(self, value: Any, parts: list[str]) -> Any:
        current = value
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    def _build_output(
        self,
        skill: Skill,
        context: dict[str, Any],
        node_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if skill.outputs:
            resolved = self._resolve_value(skill.outputs, context)
            return resolved if isinstance(resolved, dict) else {"value": resolved}
        if not node_results:
            return {}
        output = node_results[-1].get("output") or {}
        return output if isinstance(output, dict) else {"value": output}

    def _failed_node_result(
        self,
        node: SkillNode,
        exc: Exception,
        *,
        recovery: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        metadata = to_plain(node.metadata)
        if recovery:
            metadata["recovery"] = to_plain(recovery)
        return {
            "node_id": node.id,
            "type": node.type,
            "action": node.action,
            "success": False,
            "started_at": now,
            "completed_at": now,
            "payload": to_plain(node.payload),
            "output": {},
            "expect": to_plain(node.expect),
            "validation": {"success": False, "errors": [str(exc)]},
            "error": str(exc),
            "metadata": metadata,
        }

    def _get_skill(self, skill_id: str) -> Skill:
        skill = self.skills.get(skill_id)
        if skill is None:
            raise KeyError(f"Skill not found: {skill_id}")
        return skill

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _flatten_text(self, value: Any) -> str:
        plain = to_plain(value)
        if plain is None:
            return ""
        if isinstance(plain, (str, int, float, bool)):
            return str(plain)
        if isinstance(plain, dict):
            return " ".join(self._flatten_text(item) for item in plain.values())
        if isinstance(plain, list):
            return " ".join(self._flatten_text(item) for item in plain)
        return str(plain)

    def _find_key(self, value: Any, wanted_key: str) -> Any:
        plain = to_plain(value)
        if isinstance(plain, dict):
            if wanted_key in plain:
                return plain[wanted_key]
            for item in plain.values():
                found = self._find_key(item, wanted_key)
                if found is not None:
                    return found
        if isinstance(plain, list):
            for item in plain:
                found = self._find_key(item, wanted_key)
                if found is not None:
                    return found
        return None

    def _element_exists(self, output: Any) -> bool:
        plain = to_plain(output)
        if not plain:
            return False
        if isinstance(plain, dict):
            best_match = plain.get("best_match")
            if best_match:
                return True
            matches = plain.get("matches")
            if isinstance(matches, list) and len(matches) > 0:
                return True
            elements = plain.get("elements")
            if isinstance(elements, list) and len(elements) > 0:
                return True
        return False
