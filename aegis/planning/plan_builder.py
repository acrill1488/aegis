from __future__ import annotations

from typing import Any

from .models import ExecutionGraph, PlanStep, Task


class PlanBuilder:
    """Build declarative execution graphs from Tasks.

    PlanBuilder may inspect Capability Runtime for capability availability, but
    it never invokes capabilities. Missing capabilities are represented as
    step metadata so the graph remains reviewable.
    """

    def build(
        self,
        task: Task,
        capability_runtime: Any | None = None,
    ) -> ExecutionGraph:
        goal = task.goal.casefold()

        if "presentation" in goal or "\u043f\u0440\u0435\u0437\u0435\u043d\u0442\u0430\u0446" in goal:
            steps = [
                self._step(
                    "step_context",
                    "windows.context.snapshot",
                    capability_runtime=capability_runtime,
                ),
                self._step(
                    "step_system",
                    "windows.system.status",
                    capability_runtime=capability_runtime,
                ),
                self._step(
                    "step_outline",
                    "echo",
                    dependencies=["step_context", "step_system"],
                    inputs={"message": "Create presentation outline placeholder"},
                    capability_runtime=capability_runtime,
                ),
            ]
            return self._graph(steps)

        if "research" in goal or "\u0438\u0441\u0441\u043b\u0435\u0434" in goal:
            steps = [
                self._step(
                    "step_context",
                    "windows.context.snapshot",
                    capability_runtime=capability_runtime,
                ),
                self._step(
                    "step_research_placeholder",
                    "echo",
                    dependencies=["step_context"],
                    inputs={"message": "Research placeholder"},
                    capability_runtime=capability_runtime,
                ),
            ]
            return self._graph(steps)

        return self._graph(
            [
                self._step(
                    "step_echo",
                    "echo",
                    inputs={"message": task.goal},
                    capability_runtime=capability_runtime,
                )
            ]
        )

    def _step(
        self,
        step_id: str,
        capability_id: str,
        *,
        dependencies: list[str] | None = None,
        inputs: dict[str, Any] | None = None,
        capability_runtime: Any | None = None,
    ) -> PlanStep:
        metadata: dict[str, Any] = {}
        if not self._capability_exists(capability_runtime, capability_id):
            metadata["missing_capability"] = True

        return PlanStep(
            id=step_id,
            capability_id=capability_id,
            dependencies=list(dependencies or []),
            inputs=dict(inputs or {}),
            metadata=metadata,
        )

    def _capability_exists(
        self,
        capability_runtime: Any | None,
        capability_id: str,
    ) -> bool:
        if capability_runtime is None or not hasattr(capability_runtime, "resolve"):
            return True
        return capability_runtime.resolve(capability_id) is not None

    def _graph(self, steps: list[PlanStep]) -> ExecutionGraph:
        return ExecutionGraph(
            nodes=steps,
            edges=[
                [dependency, step.id]
                for step in steps
                for dependency in step.dependencies
            ],
        )
