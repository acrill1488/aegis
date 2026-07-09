from __future__ import annotations

from typing import Any

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
        matcher: RuleBasedSkillMatcher | None = None,
    ):
        self.core = core
        self.skill_engine = skill_engine or getattr(core, "skill_engine", None)
        if self.skill_engine is None:
            self.skill_engine = SkillEngineRuntime(core)
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
        result = self.skill_engine.run(goal.selected_skill, goal.inputs)
        return {
            "goal": goal,
            "success": result.success,
            "error": result.error,
            "result": result,
        }
