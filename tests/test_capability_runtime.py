from dataclasses import dataclass
from datetime import datetime

from aegis.agents.runtime import (
    AgentCapability,
    AgentDescriptor,
    AgentRuntime,
    BaseAgent,
    AgentHealth,
    AgentHealthState,
    AgentInvocationResult,
)
from aegis.capabilities import (
    CapabilityInvocationRequest,
    CapabilityRuntime,
    capability,
    discover_capabilities,
)


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


class DecoratedAgent(BaseAgent):
    def __init__(self):
        self.descriptor = AgentDescriptor(
            id="decorated-agent",
            name="Decorated Agent",
            version="1",
            machine_id="test-machine",
            capabilities=[],
            health=AgentHealth(AgentHealthState.healthy),
        )

    @capability(
        "demo.echo",
        name="Demo Echo",
        permissions=["demo.echo"],
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tags=["demo"],
        metadata={"sensitivity": "test"},
    )
    def echo(self, payload):
        return {"echo": payload}


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


def test_discover_capabilities_finds_decorated_agent_method():
    discovered = discover_capabilities(DecoratedAgent())
    descriptors = {item.descriptor.id: item for item in discovered}

    assert "demo.echo" in descriptors
    assert descriptors["demo.echo"].descriptor.name == "Demo Echo"
    assert descriptors["demo.echo"].descriptor.owner_agent == "decorated-agent"
    assert descriptors["demo.echo"].descriptor.permissions == ["demo.echo"]
    assert descriptors["demo.echo"].provider_handle["handler_name"] == "echo"


def test_agent_runtime_automatically_registers_decorated_capabilities():
    class Core:
        events = None

    core = Core()
    core.agent_runtime = AgentRuntime(core)
    core.capability_runtime = CapabilityRuntime(core)

    core.agent_runtime.register(DecoratedAgent())

    descriptors = {descriptor.id: descriptor for descriptor in core.capability_runtime.list()}
    assert descriptors["demo.echo"].metadata["sensitivity"] == "test"

    result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="demo.echo",
            payload={"message": "hello"},
        )
    )

    assert result.success is True
    assert result.output == {"echo": {"message": "hello"}}
