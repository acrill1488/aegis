from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .context import PlannerContextBuilder
from .graph import PlannerGraph
from .heuristics import build_steps
from .models import PlannerContext, PlannerPlan, PlannerStep, utc_now


DEFAULT_PLANNER_ROOT = Path(r"F:\AI_WORKSPACE\planner")


class AdaptivePlannerRuntime:
    """Heuristic-only planner that builds declarative skill graphs from context."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        root: str | Path = DEFAULT_PLANNER_ROOT,
        context_builder: PlannerContextBuilder | None = None,
    ):
        self.core = core
        self.root = Path(root)
        self.plan_path = self.root / "plans.json"
        self.context_builder = context_builder or PlannerContextBuilder(core)

    def build_context(self, goal: str) -> PlannerContext:
        return self.context_builder.build(goal)

    def plan(self, goal: str) -> PlannerPlan:
        context = self.build_context(goal)
        steps = build_steps(context)
        warnings: list[str] = []
        for step in steps:
            self._apply_reflection(step, context, warnings)
            self._apply_operational_memory(step, context)
            step.confidence = round(min(max(step.confidence, 0.0), 1.0), 3)

        graph = PlannerGraph(nodes=steps)
        graph.validate()
        plan = PlannerPlan(
            goal=goal,
            context=context,
            graph=graph,
            warnings=warnings,
            metadata={
                "planner": "adaptive_v1",
                "llm_used": False,
                "topological_order": graph.topological_order(),
            },
        )
        self._store_plan(plan)
        self._publish(
            "planner.plan.created",
            {
                "plan_id": plan.id,
                "goal": plan.goal,
                "step_count": len(plan.graph.nodes),
                "warnings": plan.warnings,
            },
            plan=plan,
        )
        return plan

    def validate(self, plan: PlannerPlan | str) -> dict[str, Any]:
        resolved = self._resolve_plan(plan)
        errors: list[str] = []
        try:
            if resolved.graph is None:
                raise ValueError("Plan has no graph")
            resolved.graph.validate()
        except ValueError as exc:
            errors.append(str(exc))

        resolved.status = "validated" if not errors else "invalid"
        resolved.validated_at = utc_now()
        self._store_plan(resolved)
        result = {
            "plan_id": resolved.id,
            "valid": not errors,
            "errors": errors,
            "warnings": list(resolved.warnings),
            "topological_order": (
                resolved.graph.topological_order()
                if resolved.graph is not None and not errors
                else []
            ),
        }
        self._publish(
            "planner.plan.validated",
            result,
            plan=resolved,
            severity="info" if result["valid"] else "error",
        )
        return result

    def explain(self, plan: PlannerPlan | str) -> str:
        resolved = self._resolve_plan(plan)
        if resolved.graph is None:
            return f"Plan {resolved.id} has no graph."

        lines = [
            f"Plan {resolved.id}",
            f"Goal: {resolved.goal}",
            f"Planner: {resolved.metadata.get('planner', 'adaptive_v1')}",
            "LLM used: no",
            "",
            "Steps:",
        ]
        for node in resolved.graph.nodes:
            warnings = node.metadata.get("warnings") or []
            warning_text = f" warnings={warnings}" if warnings else ""
            lines.append(
                "- "
                f"{node.id}: {node.title} "
                f"skill={node.skill_id} "
                f"confidence={node.confidence}"
                f"{warning_text}"
            )
        if resolved.context is not None:
            lines.extend(
                [
                    "",
                    "Context:",
                    f"- project_id: {resolved.context.project_id or 'none'}",
                    f"- knowledge_hits: {len(resolved.context.knowledge_hits)}",
                    f"- reflection_reports: {len(resolved.context.reflection_reports)}",
                    f"- memory_hits: {len(resolved.context.memory_hits)}",
                    f"- recent_missions: {len(resolved.context.recent_missions)}",
                ]
            )
        if resolved.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in resolved.warnings)
        return "\n".join(lines)

    def get_plan(self, plan_id: str) -> PlannerPlan:
        plans = self._load_plans()
        if plan_id not in plans:
            raise KeyError(f"Planner plan not found: {plan_id}")
        return plans[plan_id]

    def _apply_reflection(
        self,
        step: PlannerStep,
        context: PlannerContext,
        warnings: list[str],
    ) -> None:
        for report in context.reflection_reports:
            recommendations = report.get("recommendations") or []
            if not isinstance(recommendations, list):
                continue
            for recommendation in recommendations:
                if not isinstance(recommendation, dict):
                    continue
                target = str(recommendation.get("target") or "")
                metadata = recommendation.get("metadata") or {}
                skill_target = str(metadata.get("skill_id") or target)
                if skill_target != step.skill_id:
                    continue
                reason = str(recommendation.get("reason") or "Reflection recommends review.")
                step.confidence -= 0.15
                step.metadata.setdefault("warnings", []).append(reason)
                warnings.append(f"{step.skill_id}: {reason}")

    def _apply_operational_memory(
        self,
        step: PlannerStep,
        context: PlannerContext,
    ) -> None:
        success_count = 0
        failure_count = 0
        for record in context.memory_hits:
            record_type = str(record.get("type") or "")
            source = str(record.get("source") or "")
            data = record.get("data") if isinstance(record.get("data"), dict) else {}
            skill_id = str(data.get("skill_id") or source)
            if skill_id != step.skill_id:
                continue
            if record_type == "skill.success":
                success_count += 1
            elif record_type == "skill.failure":
                failure_count += 1

        total = success_count + failure_count
        if total == 0:
            return
        success_rate = success_count / total
        step.metadata["operational_memory"] = {
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": round(success_rate, 3),
        }
        if total >= 2 and success_rate >= 0.75:
            step.confidence += 0.1
        elif total >= 2 and success_rate <= 0.4:
            step.confidence -= 0.1

    def _resolve_plan(self, plan: PlannerPlan | str) -> PlannerPlan:
        if isinstance(plan, PlannerPlan):
            return plan
        return self.get_plan(plan)

    def _store_plan(self, plan: PlannerPlan) -> None:
        plans = self._load_raw_plans()
        plans[plan.id] = self._to_dict(plan)
        self.root.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(
            json.dumps(plans, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_plans(self) -> dict[str, PlannerPlan]:
        return {
            plan_id: self._plan_from_dict(data)
            for plan_id, data in self._load_raw_plans().items()
            if isinstance(data, dict)
        }

    def _load_raw_plans(self) -> dict[str, Any]:
        if not self.plan_path.exists():
            return {}
        try:
            data = json.loads(self.plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _to_dict(self, value: Any) -> Any:
        if isinstance(value, PlannerGraph):
            return {
                "nodes": [self._to_dict(node) for node in value.nodes],
                "edges": [[source, target] for source, target in value.edges],
            }
        if is_dataclass(value):
            return {field.name: self._to_dict(getattr(value, field.name)) for field in fields(value)}
        if isinstance(value, datetime):
            return value.isoformat()
        return to_plain(value)

    def _plan_from_dict(self, data: dict[str, Any]) -> PlannerPlan:
        context_data = data.get("context") if isinstance(data.get("context"), dict) else {}
        graph_data = data.get("graph") if isinstance(data.get("graph"), dict) else {}
        nodes = [
            PlannerStep(
                id=str(item.get("id") or ""),
                title=str(item.get("title") or ""),
                skill_id=str(item.get("skill_id") or ""),
                priority=int(item.get("priority", 50)),
                dependencies=[str(dep) for dep in item.get("dependencies") or []],
                estimated_duration=(
                    float(item["estimated_duration"])
                    if item.get("estimated_duration") is not None
                    else None
                ),
                confidence=float(item.get("confidence", 0.5)),
                metadata=dict(item.get("metadata") or {}),
            )
            for item in graph_data.get("nodes") or []
            if isinstance(item, dict)
        ]
        edges = [
            (str(edge[0]), str(edge[1]))
            for edge in graph_data.get("edges") or []
            if isinstance(edge, (list, tuple)) and len(edge) == 2
        ]
        validated_at = data.get("validated_at")
        return PlannerPlan(
            id=str(data.get("id") or ""),
            goal=str(data.get("goal") or ""),
            context=PlannerContext(
                goal=str(context_data.get("goal") or data.get("goal") or ""),
                project_id=(
                    str(context_data.get("project_id"))
                    if context_data.get("project_id") is not None
                    else None
                ),
                knowledge_hits=list(context_data.get("knowledge_hits") or []),
                reflection_reports=list(context_data.get("reflection_reports") or []),
                memory_hits=list(context_data.get("memory_hits") or []),
                recent_missions=list(context_data.get("recent_missions") or []),
                metadata=dict(context_data.get("metadata") or {}),
            ),
            graph=PlannerGraph(nodes=nodes, edges=edges),
            status=str(data.get("status") or "created"),
            warnings=[str(item) for item in data.get("warnings") or []],
            created_at=self._parse_datetime(data.get("created_at")),
            validated_at=self._parse_datetime(validated_at) if validated_at else None,
            metadata=dict(data.get("metadata") or {}),
        )

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return utc_now()

    def _publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        plan: PlannerPlan | None = None,
        severity: str = "info",
    ) -> None:
        event_platform = getattr(self.core, "event_platform", None)
        publish = getattr(event_platform, "publish", None)
        if not callable(publish):
            return
        project_id = plan.context.project_id if plan and plan.context else None
        try:
            publish(
                event_type,
                "adaptive_planner",
                payload,
                severity=severity,
                project_id=project_id,
                correlation_id=plan.metadata.get("correlation_id") if plan else None,
            )
        except Exception:
            return
