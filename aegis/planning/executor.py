from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aegis.capabilities import CapabilityInvocationRequest
from aegis.serialization import to_plain

from .models import Plan, PlanExecution, PlanStep, StepExecutionState


class PlanExecutor:
    """Sequential DAG executor for Task Planning Runtime plans.

    Stage 3 intentionally keeps execution small: no retry, no parallelism, no
    recovery. Each ready step is invoked through Capability Runtime and then
    validated with the simple success-based validator.
    """

    def __init__(
        self,
        *,
        capability_runtime: Any,
        plans: dict[str, Plan] | None = None,
        event_bus: Any | None = None,
        save_plan: Callable[[Plan], None] | None = None,
        save_execution: Callable[[PlanExecution], None] | None = None,
    ):
        self.capability_runtime = capability_runtime
        self.plans = plans if plans is not None else {}
        self.event_bus = event_bus
        self.save_plan = save_plan
        self.save_execution = save_execution
        self.plan: Plan | None = None
        self.execution: PlanExecution | None = None

    def execute(self, plan_id: str) -> PlanExecution:
        plan = self.plans.get(plan_id)
        if plan is None:
            raise KeyError(f"Plan not found: {plan_id}")
        return self.execute_plan(plan)

    def execute_plan(self, plan: Plan) -> PlanExecution:
        self._validate_plan(plan)
        trace_id = str(plan.metadata.get("trace_id") or uuid4())
        execution = PlanExecution(
            execution_id=f"execution_{uuid4().hex}",
            plan_id=plan.id,
            task_id=plan.task_id,
            trace_id=trace_id,
        )
        self.plan = plan
        self.execution = execution

        plan.status = "running"
        execution.status = "running"
        execution.started_at = self._now()
        self._save_plan(plan)
        self._save_execution(execution)
        self._publish("planning.started", {"plan": plan, "execution": execution})

        while not self._is_complete(plan, execution):
            ready = self.ready_steps()
            if not ready:
                execution.error = "No ready steps remain; dependencies are blocked."
                self._fail_plan(plan, execution)
                return execution

            step_state = self.execute_step(ready[0])
            if step_state.status == "failed":
                self._fail_plan(plan, execution)
                return execution

        plan.status = "completed"
        execution.status = "completed"
        execution.completed_at = self._now()
        self._save_plan(plan)
        self._save_execution(execution)
        self._publish("planning.completed", {"plan": plan, "execution": execution})
        return execution

    def execute_step(self, step: PlanStep) -> StepExecutionState:
        if self.plan is None or self.execution is None:
            raise RuntimeError("No active plan execution.")
        if not self.is_step_ready(step):
            raise ValueError(f"Step is not ready: {step.id}")

        started_at = self._now()
        self._publish(
            "planning.step.started",
            {"plan": self.plan, "execution": self.execution, "step": step},
        )
        request = CapabilityInvocationRequest(
            capability_id=step.capability_id,
            payload=dict(step.inputs),
            caller="planning.executor",
            trace_id=self.execution.trace_id,
            timeout_ms=self._timeout_ms(step),
            metadata={
                "plan_id": self.plan.id,
                "execution_id": self.execution.execution_id,
                "step_id": step.id,
                "step_metadata": dict(step.metadata),
            },
        )
        result = self.capability_runtime.invoke(request)
        validation = self._validate_step_result(result)

        if validation["success"]:
            return self.mark_completed(step, result, started_at, validation)
        return self.mark_failed(step, result, started_at, validation)

    def ready_steps(self) -> list[PlanStep]:
        if self.plan is None:
            return []
        return [
            step
            for step in self.plan.graph.nodes
            if self.is_step_ready(step)
        ]

    def is_step_ready(self, step: PlanStep) -> bool:
        if self.execution is None:
            return False
        if step.id in self.execution.step_states:
            return False
        return all(
            self.execution.step_states.get(dependency) is not None
            and self.execution.step_states[dependency].status == "completed"
            for dependency in step.dependencies
        )

    def mark_completed(
        self,
        step: PlanStep,
        result: Any,
        started_at: datetime | None = None,
        validation: dict[str, Any] | None = None,
    ) -> StepExecutionState:
        state = self._step_state(
            step=step,
            status="completed",
            result=result,
            started_at=started_at,
            validation=validation,
        )
        self._record_step_state(state)
        self._publish(
            "planning.step.completed",
            {"plan": self.plan, "execution": self.execution, "step_state": state},
        )
        return state

    def mark_failed(
        self,
        step: PlanStep,
        result: Any,
        started_at: datetime | None = None,
        validation: dict[str, Any] | None = None,
    ) -> StepExecutionState:
        state = self._step_state(
            step=step,
            status="failed",
            result=result,
            started_at=started_at,
            validation=validation,
        )
        self._record_step_state(state)
        self._publish(
            "planning.step.failed",
            {"plan": self.plan, "execution": self.execution, "step_state": state},
        )
        return state

    def _validate_plan(self, plan: Plan) -> None:
        step_ids = {step.id for step in plan.graph.nodes}
        if len(step_ids) != len(plan.graph.nodes):
            raise ValueError("Plan contains duplicate step ids.")

        for step in plan.graph.nodes:
            missing = [item for item in step.dependencies if item not in step_ids]
            if missing:
                raise ValueError(
                    f"Step {step.id} has unknown dependencies: {', '.join(missing)}"
                )

        visiting: set[str] = set()
        visited: set[str] = set()
        steps = {step.id: step for step in plan.graph.nodes}

        def visit(step_id: str) -> None:
            if step_id in visited:
                return
            if step_id in visiting:
                raise ValueError("Plan graph contains a cycle.")
            visiting.add(step_id)
            for dependency in steps[step_id].dependencies:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in step_ids:
            visit(step_id)

    def _validate_step_result(self, result: Any) -> dict[str, Any]:
        success = bool(getattr(result, "success", False))
        return {
            "success": success,
            "status": "completed" if success else "failed",
        }

    def _step_state(
        self,
        *,
        step: PlanStep,
        status: str,
        result: Any,
        started_at: datetime | None,
        validation: dict[str, Any] | None,
    ) -> StepExecutionState:
        return StepExecutionState(
            step_id=step.id,
            status=status,
            attempt=1,
            started_at=started_at or self._now(),
            completed_at=self._now(),
            input_snapshot=to_plain(step.inputs),
            output=to_plain(getattr(result, "output", {}) or {}),
            error=getattr(result, "error", None),
            validation=dict(validation or {}),
            metadata={
                "capability_id": step.capability_id,
                "capability_result": to_plain(result),
            },
        )

    def _record_step_state(self, state: StepExecutionState) -> None:
        if self.execution is None:
            raise RuntimeError("No active plan execution.")
        self.execution.step_states[state.step_id] = state
        self._save_execution(self.execution)

    def _fail_plan(self, plan: Plan, execution: PlanExecution) -> None:
        plan.status = "failed"
        execution.status = "failed"
        execution.completed_at = self._now()
        self._save_plan(plan)
        self._save_execution(execution)
        self._publish("planning.failed", {"plan": plan, "execution": execution})

    def _is_complete(self, plan: Plan, execution: PlanExecution) -> bool:
        return all(
            execution.step_states.get(step.id) is not None
            and execution.step_states[step.id].status == "completed"
            for step in plan.graph.nodes
        )

    def _timeout_ms(self, step: PlanStep) -> int:
        value = step.timeout.get("timeout_ms", 30000)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 30000

    def _save_plan(self, plan: Plan) -> None:
        if self.save_plan is not None:
            self.save_plan(plan)

    def _save_execution(self, execution: PlanExecution) -> None:
        if self.save_execution is not None:
            self.save_execution(execution)

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.event_bus is None or not hasattr(self.event_bus, "publish"):
            return
        plan_id = payload.get("plan").id if payload.get("plan") is not None else "unknown"
        trace_id = None
        if self.execution is not None:
            trace_id = self.execution.trace_id
        try:
            self.event_bus.publish(
                event_type,
                source=f"planning.executor:{plan_id}",
                payload=to_plain(payload),
                trace_id=trace_id,
            )
        except Exception:
            return

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
