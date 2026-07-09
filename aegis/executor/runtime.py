from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aegis.capabilities import CapabilityInvocationRequest
from aegis.serialization import to_plain

from .models import ExecutionPlan, ExecutionResult, ExecutionStep
from .validator import ExecutorValidator, ValidationResult


class ExecutorRuntime:
    """Observe/Reason/Action/Validate executor.

    Actions are invoked through Capability Runtime when they reference external
    work. Observe and validation remain side-effect-free unless a plan
    explicitly routes observation through a public capability such as ui.observe.
    """

    def __init__(
        self,
        capability_runtime: Any | None = None,
        validator: ExecutorValidator | None = None,
        core: Any | None = None,
    ):
        self.core = core
        self.capability_runtime = capability_runtime
        self.validator = validator or ExecutorValidator()
        self.plan: ExecutionPlan | None = None
        self.history: list[dict[str, Any]] = []

    def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        self.plan = plan
        self.history = list(plan.history)
        completed_steps: list[str] = []
        plan.status = "running"

        for index, step in enumerate(plan.steps):
            plan.current_step = index
            step_result = self.execute_step(step)
            if not step_result["success"]:
                plan.status = "failed"
                plan.history = list(self.history)
                return ExecutionResult(
                    success=False,
                    completed_steps=completed_steps,
                    failed_step=step.id,
                    history=list(self.history),
                )
            completed_steps.append(step.id)

        plan.status = "completed"
        plan.history = list(self.history)
        return ExecutionResult(
            success=True,
            completed_steps=completed_steps,
            history=list(self.history),
        )

    def execute_step(self, step: ExecutionStep) -> dict[str, Any]:
        attempts = max(1, int(step.retry_limit) + 1)
        last_validation = ValidationResult(False, "not_run", "Step was not run.")

        for attempt in range(1, attempts + 1):
            before = self.observe(step.observe, step=step, phase="before")
            self.reason(step)
            action_result = self.action(step)
            after = self.observe(step.observe, step=step, phase="after")
            last_validation = self.validate(
                step.validate,
                before=before,
                after=after,
                action_result=action_result,
                step=step,
                attempt=attempt,
            )
            if last_validation.success:
                self._record(
                    "step.completed",
                    step=step,
                    attempt=attempt,
                    validation=last_validation,
                )
                return {
                    "success": True,
                    "attempt": attempt,
                    "validation": to_plain(last_validation),
                    "action_result": to_plain(action_result),
                }
            if attempt < attempts:
                self.retry(step, attempt, last_validation)

        self._record(
            "step.failed",
            step=step,
            attempt=attempts,
            validation=last_validation,
        )
        return {
            "success": False,
            "attempt": attempts,
            "validation": to_plain(last_validation),
        }

    def observe(
        self,
        observe: Any = None,
        *,
        step: ExecutionStep | None = None,
        phase: str = "observe",
    ) -> Any:
        observation = self._run_callable_or_capability(observe, step=step)
        if observation is None:
            observation = {}
        self._record(phase, step=step, observation=observation)
        return observation

    def reason(self, step: ExecutionStep) -> Any:
        reasoning = step.reason
        if callable(reasoning):
            reasoning = reasoning(step)
        if reasoning is None:
            reasoning = step.description
        self._record("reason", step=step, reason=reasoning)
        return reasoning

    def action(self, step: ExecutionStep) -> Any:
        result = self._run_callable_or_capability(
            step.action,
            step=step,
            default_payload=dict(step.metadata.get("payload", {})),
        )
        self._record("action", step=step, result=result)
        return result

    def validate(
        self,
        validate: Any = None,
        *,
        before: Any = None,
        after: Any = None,
        action_result: Any = None,
        step: ExecutionStep | None = None,
        attempt: int = 1,
    ) -> ValidationResult:
        result = self.validator.validate(
            validate,
            before=before,
            after=after,
            action_result=action_result,
            context={"step": step, "attempt": attempt, "runtime": self},
        )
        self._record("validate", step=step, attempt=attempt, validation=result)
        return result

    def retry(
        self,
        step: ExecutionStep,
        attempt: int,
        validation: ValidationResult | None = None,
    ) -> None:
        self._record("retry", step=step, attempt=attempt, validation=validation)

    def execute_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self.plan_from_payload(payload)
        return to_plain(self.execute(plan))

    def validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self.plan_from_payload(payload)
        return self.validate_plan(plan)

    def dry_run_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return self.dry_run(self.plan_from_payload(payload))

    def dry_run(self, plan: ExecutionPlan) -> list[dict[str, Any]]:
        return [
            {
                "step": index,
                "id": step.id,
                "description": step.description,
                "observe": to_plain(step.observe),
                "action": to_plain(step.action),
                "expected_validation": to_plain(step.validate),
            }
            for index, step in enumerate(plan.steps, start=1)
        ]

    def validate_plan(self, plan: ExecutionPlan) -> dict[str, Any]:
        errors = []
        step_ids = set()
        for step in plan.steps:
            if not step.id:
                errors.append("Step id is required.")
            if step.id in step_ids:
                errors.append(f"Duplicate step id: {step.id}")
            step_ids.add(step.id)
            if step.retry_limit < 0:
                errors.append(f"Step {step.id} retry_limit must be >= 0.")
        return {
            "success": not errors,
            "status": "valid" if not errors else "invalid",
            "errors": errors,
            "steps": len(plan.steps),
        }

    def plan_from_payload(self, payload: dict[str, Any]) -> ExecutionPlan:
        if "plan" in payload and isinstance(payload["plan"], ExecutionPlan):
            return payload["plan"]
        if "plan" in payload and isinstance(payload["plan"], dict):
            return self._plan_from_dict(payload["plan"])
        if "goal" in payload or "steps" in payload:
            return self._plan_from_dict(payload)
        plan_id = payload.get("plan_id")
        if plan_id and self.core is not None:
            planning = getattr(self.core, "task_planning_runtime", None)
            planning_plan = planning.get_plan(str(plan_id)) if planning else None
            if planning_plan is not None:
                return self.from_planning_plan(planning_plan)
        raise ValueError("Executor payload must include plan, goal/steps, or plan_id.")

    def from_planning_plan(self, plan: Any) -> ExecutionPlan:
        steps = []
        for node in getattr(getattr(plan, "graph", None), "nodes", []):
            validation = dict(getattr(node, "metadata", {}) or {}).get("validate")
            retry_policy = dict(getattr(node, "retry_policy", {}) or {})
            retry_limit = retry_policy.get("retry_limit", retry_policy.get("max_attempts", 1))
            try:
                retry_limit = max(0, int(retry_limit) - 1)
            except (TypeError, ValueError):
                retry_limit = 0
            steps.append(
                ExecutionStep(
                    id=str(node.id),
                    description=str(getattr(node, "capability_id", node.id)),
                    observe=dict(getattr(node, "metadata", {}) or {}).get("observe"),
                    reason=f"Invoke capability {node.capability_id}",
                    action={
                        "capability_id": node.capability_id,
                        "payload": dict(getattr(node, "inputs", {}) or {}),
                    },
                    validate=validation,
                    retry_limit=retry_limit,
                    timeout=getattr(node, "timeout", None),
                    metadata={
                        "planning_plan_id": getattr(plan, "id", ""),
                        "planning_task_id": getattr(plan, "task_id", ""),
                        "planning_step": to_plain(node),
                    },
                )
            )
        return ExecutionPlan(
            goal=str(getattr(plan, "task_id", getattr(plan, "id", ""))),
            steps=steps,
            status=str(getattr(plan, "status", "created")),
            history=[],
        )

    def _plan_from_dict(self, data: dict[str, Any]) -> ExecutionPlan:
        return ExecutionPlan(
            goal=str(data.get("goal", "")),
            steps=[
                self._step_from_dict(item)
                for item in data.get("steps", [])
                if isinstance(item, dict)
            ],
            current_step=int(data.get("current_step", 0) or 0),
            status=str(data.get("status", "created")),
            history=list(data.get("history", []) or []),
        )

    def _step_from_dict(self, data: dict[str, Any]) -> ExecutionStep:
        return ExecutionStep(
            id=str(data.get("id", "")),
            description=str(data.get("description", "")),
            observe=data.get("observe"),
            reason=data.get("reason"),
            action=data.get("action"),
            validate=data.get("validate"),
            retry_limit=int(data.get("retry_limit", 0) or 0),
            timeout=data.get("timeout"),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    def _run_callable_or_capability(
        self,
        spec: Any,
        *,
        step: ExecutionStep | None,
        default_payload: dict[str, Any] | None = None,
    ) -> Any:
        if callable(spec):
            return spec(step)
        if spec in (None, {}, []):
            return {}
        if isinstance(spec, str):
            spec = {"capability_id": spec, "payload": default_payload or {}}
        if isinstance(spec, dict) and spec.get("capability_id"):
            if self.capability_runtime is None:
                raise RuntimeError("Capability Runtime is required for executor actions.")
            result = self.capability_runtime.invoke(
                CapabilityInvocationRequest(
                    capability_id=str(spec["capability_id"]),
                    payload=dict(spec.get("payload", default_payload or {}) or {}),
                    caller="executor.runtime",
                    timeout_ms=self._timeout_ms(step),
                    metadata={
                        "executor_step_id": step.id if step is not None else None,
                    },
                )
            )
            return result
        return spec

    def _timeout_ms(self, step: ExecutionStep | None) -> int:
        timeout = step.timeout if step is not None else None
        if isinstance(timeout, dict):
            timeout = timeout.get("timeout_ms", 30000)
        try:
            return int(timeout or 30000)
        except (TypeError, ValueError):
            return 30000

    def _record(self, event: str, step: ExecutionStep | None = None, **payload: Any) -> None:
        self.history.append(
            {
                "event": event,
                "step_id": step.id if step is not None else None,
                **to_plain(payload),
            }
        )
