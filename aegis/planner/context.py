from __future__ import annotations

from typing import Any

from aegis.serialization import to_plain

from .models import PlannerContext


class PlannerContextBuilder:
    def __init__(self, core: Any | None = None):
        self.core = core

    def build(self, goal: str) -> PlannerContext:
        project = self._active_project()
        project_id = getattr(project, "id", None)
        context = PlannerContext(
            goal=goal,
            project_id=project_id,
            knowledge_hits=self._knowledge_hits(goal),
            reflection_reports=self._reflection_reports(),
            memory_hits=self._memory_hits(goal),
            recent_missions=self._recent_missions(),
            metadata={
                "project_active": project is not None,
                "project_name": getattr(project, "name", None),
                "project_workspace_path": getattr(project, "workspace_path", None),
            },
        )
        self._publish(
            "planner.context.created",
            {
                "goal": goal,
                "project_id": project_id,
                "knowledge_hit_count": len(context.knowledge_hits),
                "reflection_report_count": len(context.reflection_reports),
                "memory_hit_count": len(context.memory_hits),
                "recent_mission_count": len(context.recent_missions),
            },
            project_id=project_id,
        )
        return context

    def _active_project(self):
        runtime = getattr(self.core, "project_runtime", None)
        get_active = getattr(runtime, "get_active", None)
        if not callable(get_active):
            return None
        try:
            return get_active()
        except Exception:
            return None

    def _knowledge_hits(self, goal: str) -> list[dict[str, Any]]:
        runtime = getattr(self.core, "knowledge", None)
        search = getattr(runtime, "search", None)
        if not callable(search):
            return []
        try:
            return [dict(to_plain(item) or {}) for item in search(goal, limit=5)]
        except Exception:
            return []

    def _reflection_reports(self) -> list[dict[str, Any]]:
        runtime = getattr(self.core, "reflection_engine", None)
        list_reports = getattr(runtime, "list_reports", None)
        if not callable(list_reports):
            return []
        try:
            return [dict(to_plain(item) or {}) for item in list_reports(limit=5)]
        except Exception:
            return []

    def _memory_hits(self, goal: str) -> list[dict[str, Any]]:
        runtime = getattr(self.core, "operational_memory", None)
        search = getattr(runtime, "search", None)
        if not callable(search):
            return []
        try:
            return [dict(to_plain(item) or {}) for item in search(goal, limit=20)]
        except Exception:
            return []

    def _recent_missions(self) -> list[dict[str, Any]]:
        runtime = getattr(self.core, "mission_runtime", None)
        list_missions = getattr(runtime, "list", None)
        if not callable(list_missions):
            return []
        try:
            missions = list_missions()
        except Exception:
            return []
        missions = sorted(
            missions,
            key=lambda item: getattr(item, "created_at", None),
            reverse=True,
        )
        return [dict(to_plain(item) or {}) for item in missions[:5]]

    def _publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        project_id: str | None = None,
    ) -> None:
        event_platform = getattr(self.core, "event_platform", None)
        publish = getattr(event_platform, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, "adaptive_planner", payload, project_id=project_id)
        except Exception:
            return
