from .models import (
    AgentCapability,
    AgentDescriptor,
    AgentHealth,
    AgentInvocation,
    AgentInvocationResult,
    AgentStatus,
)


class BaseAgent:
    descriptor: AgentDescriptor

    def start(self) -> AgentDescriptor:
        self.descriptor.status = AgentStatus.running
        return self.descriptor

    def stop(self, reason: str = "") -> AgentDescriptor:
        self.descriptor.status = AgentStatus.stopped
        if reason:
            self.descriptor.metadata["stop_reason"] = reason
        return self.descriptor

    def health(self) -> AgentHealth:
        return self.descriptor.health

    def capabilities(self) -> list[AgentCapability]:
        return self.descriptor.capabilities

    def invoke(self, invocation: AgentInvocation) -> AgentInvocationResult:
        return AgentInvocationResult(
            success=False,
            error="Capability not implemented",
            metadata={"capability_id": invocation.capability_id},
        )
