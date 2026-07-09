from dataclasses import dataclass, field


@dataclass
class CapabilityDescriptor:
    id: str
    name: str
    version: str = "1"
    owner_agent: str = ""
    machine_scope: str = "local"
    permissions: list = field(default_factory=list)
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class CapabilityInvocationRequest:
    capability_id: str
    payload: dict = field(default_factory=dict)
    caller: str = "cli"
    trace_id: str | None = None
    timeout_ms: int = 30000
    metadata: dict = field(default_factory=dict)


@dataclass
class CapabilityInvocationResult:
    success: bool
    capability_id: str
    output: dict = field(default_factory=dict)
    error: str | None = None
    selected_route: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
