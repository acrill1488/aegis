from __future__ import annotations

from typing import Any

from aegis.mission_engine import MissionRuntime
from aegis.skill_engine import SkillEngineRuntime

from .matcher import RuleBasedSkillMatcher
from .models import Goal


class GoalEngineRuntime:
    """Parses user goals and executes matched skills through Skill Engine."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        skill_engine: SkillEngineRuntime | None = None,
        mission_runtime: MissionRuntime | None = None,
        matcher: RuleBasedSkillMatcher | None = None,
    ):
        self.core = core
        self.skill_engine = skill_engine or getattr(core, "skill_engine", None)
        if self.skill_engine is None:
            self.skill_engine = SkillEngineRuntime(core)
        self.mission_runtime = mission_runtime or getattr(core, "mission_runtime", None)
        if self.mission_runtime is None:
            self.mission_runtime = MissionRuntime(core, skill_engine=self.skill_engine)
        self.matcher = matcher or RuleBasedSkillMatcher(self.skill_engine.skills)

    def parse(self, text: str) -> Goal:
        return self.matcher.match(text)

    def execute(self, text: str) -> dict[str, Any]:
        goal = self.parse(text)
        if goal.metadata.get("status") == "unresolved":
            return {
                "goal": goal,
                "success": False,
                "error": "Goal unresolved",
                "result": None,
            }
        if goal.metadata.get("status") == "not_available":
            return {
                "goal": goal,
                "success": False,
                "error": f"Skill not available: {goal.selected_skill}",
                "result": None,
            }
        if not goal.selected_skill:
            return {
                "goal": goal,
                "success": False,
                "error": "Goal has no selected skill",
                "result": None,
            }
        mission = self.mission_runtime.create(
            goal,
            priority=int(goal.metadata.get("priority", 50)),
            metadata={"source": "goal_engine"},
        )
        mission_result = self.mission_runtime.run(mission)
        result = self._skill_result_from_mission(mission)
        return {
            "goal": goal,
            "mission": mission,
            "mission_result": mission_result,
            "success": mission_result.success,
            "error": mission_result.error,
            "result": result,
        }

    def _skill_result_from_mission(self, mission) -> Any | None:
        if not mission.graph:
            return None
        return mission.graph[-1].metadata.get("skill_result")
