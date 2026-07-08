from .base import BaseAgent
from .models import (
    AgentCapability,
    AgentDescriptor,
    AgentHealth,
    AgentHealthState,
    AgentInvocation,
    AgentInvocationResult,
)


class EchoAgent(BaseAgent):
    def __init__(self, machine_id: str = "local"):
        self.descriptor = AgentDescriptor(
            id="echo-agent",
            name="Echo Agent",
            version="1",
            machine_id=machine_id,
            capabilities=[
                AgentCapability(
                    id="echo",
                    description="Return invocation payload unchanged.",
                )
            ],
            health=AgentHealth(AgentHealthState.healthy),
            metadata={"runtime": "builtin"},
        )

    def invoke(self, invocation: AgentInvocation) -> AgentInvocationResult:
        if invocation.capability_id != "echo":
            return AgentInvocationResult(
                success=False,
                error=f"Unsupported capability: {invocation.capability_id}",
            )
        return AgentInvocationResult(success=True, output=dict(invocation.payload))
