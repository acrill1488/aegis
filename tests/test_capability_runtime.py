from dataclasses import dataclass
from datetime import datetime

from aegis.agents.runtime import (
    AgentCapability,
    AgentDescriptor,
    AgentHealth,
    AgentHealthState,
    AgentInvocationResult,
)
from aegis.capabilities import CapabilityInvocationRequest, CapabilityRuntime


WINDOWS_CAPABILITIES = {
    "windows.process.list",
    "windows.system.status",
    "windows.system.metrics",
    "windows.context.snapshot",
}


@dataclass
class SampleOutput:
    updated_at: datetime


class FakeAgentRuntime:
    def __init__(self):
        self.invocations = []
        self.descriptor = AgentDescriptor(
            id="windows-agent",
            name="Windows Agent",
            version="1",
            machine_id="test-machine",
            capabilities=[
                AgentCapability(
                    id="windows.process.list",
                    description="List local Windows processes.",
                    permissions=["windows.process.read"],
                    metadata={"sensitivity": "local_system_state"},
                ),
                AgentCapability(
                    id="windows.system.status",
                    description="Read local system status.",
                    permissions=["windows.system.read"],
                    metadata={"sensitivity": "local_system_state"},
                ),
                AgentCapability(
                    id="windows.system.metrics",
                    description="Read local system metrics.",
                    permissions=["windows.system.read"],
                    metadata={"sensitivity": "local_system_state"},
                ),
                AgentCapability(
                    id="windows.context.snapshot",
                    description="Read current live context.",
                    permissions=["live_context.read"],
                    metadata={"sensitivity": "local_context"},
                ),
            ],
            health=AgentHealth(AgentHealthState.healthy),
        )

    def list(self):
        return [self.descriptor]

    def invoke(self, agent_id, invocation):
        self.invocations.append((agent_id, invocation))
        return AgentInvocationResult(
            success=True,
            output={"sample": SampleOutput(datetime(2026, 7, 9, 12, 30, 0))},
            metadata={"handled_at": datetime(2026, 7, 9, 12, 31, 0)},
        )


class FakeCore:
    def __init__(self):
        self.agent_runtime = FakeAgentRuntime()
        self.events = None


def test_register_agent_capabilities_includes_windows_agent_capabilities():
    runtime = CapabilityRuntime(FakeCore())
    runtime.register_agent_capabilities()

    descriptors = {descriptor.id: descriptor for descriptor in runtime.list()}

    assert WINDOWS_CAPABILITIES <= set(descriptors)
    assert descriptors["windows.process.list"].owner_agent == "windows-agent"
    assert descriptors["windows.system.status"].permissions == ["windows.system.read"]
    assert (
        descriptors["windows.context.snapshot"].metadata["description"]
        == "Read current live context."
    )


def test_agent_backed_invoke_returns_json_safe_plain_output():
    core = FakeCore()
    runtime = CapabilityRuntime(core)
    runtime.register_agent_capabilities()

    result = runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="windows.context.snapshot",
            payload={},
        )
    )

    assert result.success is True
    assert result.output == {"sample": {"updated_at": "2026-07-09T12:30:00"}}
    assert result.metadata == {"handled_at": "2026-07-09T12:31:00"}
    assert result.selected_route["provider_handle"]["agent_id"] == "windows-agent"
    assert core.agent_runtime.invocations[0][1].capability_id == "windows.context.snapshot"
