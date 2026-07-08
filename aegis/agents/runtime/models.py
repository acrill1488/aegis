from dataclasses import field, dataclass
from enum import Enum


class AgentStatus(Enum):
    created = "created"
    registered = "registered"
    starting = "starting"
    running = "running"
    degraded = "degraded"
    stopping = "stopping"
    stopped = "stopped"
    failed = "failed"


class AgentHealthState(Enum):
    healthy = "healthy"
    degraded = "degraded"
    unhealthy = "unhealthy"
    unknown = "unknown"


@dataclass
class AgentCapability:
    id: str
    version: str = "1"
    description: str = ""
    permissions: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentHealth:
    state: AgentHealthState
    message: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentDescriptor:
    id: str
    name: str
    version: str
    machine_id: str
    capabilities: list[AgentCapability]
    status: AgentStatus = AgentStatus.created
    health: AgentHealth = field(
        default_factory=lambda: AgentHealth(AgentHealthState.unknown)
    )
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentInvocation:
    capability_id: str
    payload: dict = field(default_factory=dict)
    trace_id: str | None = None


@dataclass
class AgentInvocationResult:
    success: bool
    output: dict = field(default_factory=dict)
    error: str | None = None
    metadata: dict = field(default_factory=dict)
