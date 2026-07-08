from __future__ import annotations

from .base import BaseAgent
from .models import AgentDescriptor, AgentStatus


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> AgentDescriptor:
        agent.descriptor.status = AgentStatus.registered
        self._agents[agent.descriptor.id] = agent
        return agent.descriptor

    def get(self, agent_id: str) -> BaseAgent | None:
        return self._agents.get(agent_id)

    def list(self) -> list[AgentDescriptor]:
        return [agent.descriptor for agent in self._agents.values()]

    def by_capability(self, capability_id: str) -> list[BaseAgent]:
        return [
            agent
            for agent in self._agents.values()
            if any(capability.id == capability_id for capability in agent.capabilities())
        ]
