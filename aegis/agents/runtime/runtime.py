from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from .base import BaseAgent
from .models import (
    AgentDescriptor,
    AgentHealth,
    AgentHealthState,
    AgentInvocation,
    AgentInvocationResult,
    AgentStatus,
)
from .registry import AgentRegistry


class AgentRuntime:
    def __init__(self, core: Any):
        self.core = core
        self.registry = AgentRegistry()

    def register(self, agent: BaseAgent) -> AgentDescriptor:
        descriptor = self.registry.register(agent)
        self._publish("agent.registered", descriptor.id, {"agent": descriptor})
        return descriptor

    def start(self, agent_id: str) -> AgentDescriptor:
        agent = self._require_agent(agent_id)
        agent.descriptor.status = AgentStatus.starting
        try:
            descriptor = agent.start()
        except Exception as exc:
            agent.descriptor.status = AgentStatus.failed
            self._publish(
                "agent.failed",
                agent_id,
                {"agent": agent.descriptor, "error": str(exc), "phase": "start"},
            )
            raise

        self._publish("agent.running", agent_id, {"agent": descriptor})
        return descriptor

    def stop(self, agent_id: str, reason: str = "") -> AgentDescriptor:
        agent = self._require_agent(agent_id)
        agent.descriptor.status = AgentStatus.stopping
        try:
            descriptor = agent.stop(reason=reason)
        except Exception as exc:
            agent.descriptor.status = AgentStatus.failed
            self._publish(
                "agent.failed",
                agent_id,
                {"agent": agent.descriptor, "error": str(exc), "phase": "stop"},
            )
            raise

        self._publish(
            "agent.stopped",
            agent_id,
            {"agent": descriptor, "reason": reason},
        )
        return descriptor

    def health(self, agent_id: str) -> AgentHealth:
        agent = self.registry.get(agent_id)
        if agent is None:
            return AgentHealth(
                AgentHealthState.unknown,
                message=f"Agent not found: {agent_id}",
            )
        return agent.health()

    def list(self) -> list[AgentDescriptor]:
        return self.registry.list()

    def invoke(
        self,
        agent_id: str,
        invocation: AgentInvocation,
    ) -> AgentInvocationResult:
        agent = self._require_agent(agent_id)
        self._publish(
            "agent.capability_invoked",
            agent_id,
            {
                "agent_id": agent_id,
                "capability_id": invocation.capability_id,
                "payload": invocation.payload,
            },
            trace_id=invocation.trace_id,
        )

        try:
            result = agent.invoke(invocation)
        except Exception as exc:
            agent.descriptor.status = AgentStatus.failed
            result = AgentInvocationResult(success=False, error=str(exc))
            self._publish(
                "agent.capability_failed",
                agent_id,
                {
                    "agent_id": agent_id,
                    "capability_id": invocation.capability_id,
                    "error": str(exc),
                },
                trace_id=invocation.trace_id,
            )
            self._publish(
                "agent.failed",
                agent_id,
                {"agent": agent.descriptor, "error": str(exc), "phase": "invoke"},
                trace_id=invocation.trace_id,
            )
            return result

        event_type = (
            "agent.capability_completed"
            if result.success
            else "agent.capability_failed"
        )
        self._publish(
            event_type,
            agent_id,
            {
                "agent_id": agent_id,
                "capability_id": invocation.capability_id,
                "result": result,
            },
            trace_id=invocation.trace_id,
        )
        return result

    def _require_agent(self, agent_id: str) -> BaseAgent:
        agent = self.registry.get(agent_id)
        if agent is None:
            raise KeyError(f"Agent not found: {agent_id}")
        return agent

    def _publish(
        self,
        event_type: str,
        agent_id: str,
        payload: dict,
        trace_id: str | None = None,
    ) -> None:
        events = getattr(self.core, "events", None)
        if events is None or not hasattr(events, "publish"):
            return
        try:
            events.publish(
                event_type,
                source=f"agent_runtime:{agent_id}",
                payload=_to_plain(payload),
                trace_id=trace_id,
            )
        except Exception:
            return


def _to_plain(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _to_plain(asdict(value))
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_plain(item) for item in value)
    return value
