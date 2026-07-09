from __future__ import annotations

from typing import Any

from aegis.mission_engine import MissionRuntime
from aegis.planner import AdaptivePlannerRuntime
from aegis.skill_engine import SkillEngineRuntime

from .matcher import RuleBasedSkillMatcher
from .models import Goal


class GoalEngineRuntime:
    """Parses user goals and executes matched skills through Mission Runtime."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        skill_engine: SkillEngineRuntime | None = None,
        mission_runtime: MissionRuntime | None = None,
        matcher: RuleBasedSkillMatcher | None = None,
        adaptive_planner: AdaptivePlannerRuntime | None = None,
    ):
        self.core = core
        self.skill_engine = skill_engine or getattr(core, "skill_engine", None)
        if self.skill_engine is None:
            self.skill_engine = SkillEngineRuntime(core)
        self.mission_runtime = mission_runtime or getattr(core, "mission_runtime", None)
        if self.mission_runtime is None:
            self.mission_runtime = MissionRuntime(core, skill_engine=self.skill_engine)
        self.matcher = matcher or RuleBasedSkillMatcher(self.skill_engine.skills)
        self.adaptive_planner = adaptive_planner or getattr(core, "adaptive_planner", None)
        if self.adaptive_planner is None:
            self.adaptive_planner = AdaptivePlannerRuntime(core)

    def parse(self, text: str) -> Goal:
        plan = self.adaptive_planner.plan(text)
        if plan.graph is None or not plan.graph.nodes:
            return self.matcher.match(text)
        first_step = plan.graph.nodes[0]
        if first_step.skill_id == "planner.unresolved":
            goal = self.matcher.match(text)
            goal.metadata["planner_plan_id"] = plan.id
            return goal
        inputs = first_step.metadata.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {"goal": text}
        available = self.skill_engine.skills.get(first_step.skill_id) is not None
        return Goal(
            id=plan.id.replace("plan_", "goal_", 1),
            text=text.strip(),
            intent=str(first_step.metadata.get("heuristic") or "planned"),
            confidence=first_step.confidence,
            selected_skill=first_step.skill_id,
            inputs=inputs,
            metadata={
                "status": "matched" if available else "not_available",
                "skill_available": available,
                "planner_plan_id": plan.id,
                "planner": "adaptive_v1",
            },
        )

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
        orchestrator = getattr(self.core, "orchestrator", None)
        if orchestrator is not None:
            job = orchestrator.submit_mission(mission.id, priority=mission.priority)
            mission_result = orchestrator.run_job(job.id)
        else:
            job = None
            mission_result = self.mission_runtime.run(mission.id)
        mission = self.mission_runtime.show(mission.id)
        return {
            "goal": goal,
            "mission": mission,
            "orchestrator_job": job,
            "mission_result": mission_result,
            "success": mission_result.success,
            "error": mission_result.error,
            "result": mission_result,
        }
