from __future__ import annotations

from typing import Any
from uuid import uuid4

from aegis.goal_engine.models import Goal

from .models import Mission, MissionNode


class MissionPlanner:
    """Builds declarative Mission graphs from Goal Engine decisions."""

    def create_from_goal(
        self,
        goal: Goal,
        *,
        priority: int = 50,
        mission_id: str | None = None,
        workspace_path: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Mission:
        if not goal.selected_skill:
            raise ValueError("Goal has no selected skill")

        node = MissionNode(
            id="node_1",
            skill_id=goal.selected_skill,
            inputs=dict(goal.inputs),
            dependencies=[],
            status="pending",
            metadata={"goal_id": goal.id},
        )
        return Mission(
            id=mission_id or self._new_id(),
            goal=goal.text,
            priority=priority,
            workspace_path=workspace_path,
            graph=[node],
            metadata={
                "goal": goal,
                "intent": goal.intent,
                "confidence": goal.confidence,
                **dict(metadata or {}),
            },
        )

    def _new_id(self) -> str:
        return f"mission_{uuid4().hex}"
