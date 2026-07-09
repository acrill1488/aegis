from __future__ import annotations

from dataclasses import dataclass
from inspect import getmembers, ismethod
from typing import Any

from .decorators import CapabilityDefinition
from .models import CapabilityDescriptor


@dataclass(frozen=True)
class DiscoveredCapability:
    descriptor: CapabilityDescriptor
    provider_handle: dict
    handler_name: str | None = None


def discover_capabilities(agent: Any) -> list[DiscoveredCapability]:
    """Discover SDK and legacy capability declarations on an agent."""
    discovered: dict[str, DiscoveredCapability] = {}

    for capability in _legacy_agent_capabilities(agent):
        record = _from_legacy_capability(agent, capability)
        discovered[record.descriptor.id] = record

    for name, method in getmembers(agent, predicate=ismethod):
        definition = getattr(method, "__aegis_capability__", None)
        if definition is None:
            definition = getattr(method.__func__, "__aegis_capability__", None)
        if definition is None:
            continue

        record = _from_definition(agent, name, definition)
        discovered[record.descriptor.id] = record

    return list(discovered.values())


def get_capability_handler(agent: Any, capability_id: str) -> Any | None:
    for name, method in getmembers(agent, predicate=ismethod):
        definition = getattr(method, "__aegis_capability__", None)
        if definition is None:
            definition = getattr(method.__func__, "__aegis_capability__", None)
        if definition is not None and definition.id == capability_id:
            return getattr(agent, name)
    return None


def _legacy_agent_capabilities(agent: Any) -> list[Any]:
    descriptor = getattr(agent, "descriptor", agent)
    capabilities = getattr(descriptor, "capabilities", [])
    return list(capabilities or [])


def _from_legacy_capability(agent: Any, capability: Any) -> DiscoveredCapability:
    metadata = dict(getattr(capability, "metadata", {}) or {})
    descriptor = CapabilityDescriptor(
        id=capability.id,
        name=metadata.get("name", capability.id),
        version=getattr(capability, "version", "1"),
        owner_agent=_agent_id(agent),
        machine_scope=metadata.get("machine_scope", "local"),
        permissions=list(getattr(capability, "permissions", []) or []),
        input_schema=dict(metadata.get("input_schema", {})),
        output_schema=dict(metadata.get("output_schema", {})),
        tags=list(metadata.get("tags", [])),
        metadata={
            **metadata,
            "description": getattr(capability, "description", ""),
            "side_effects": list(getattr(capability, "side_effects", []) or []),
        },
    )
    return DiscoveredCapability(
        descriptor=descriptor,
        provider_handle=_agent_provider_handle(agent, descriptor.id),
    )


def _from_definition(
    agent: Any,
    handler_name: str,
    definition: CapabilityDefinition,
) -> DiscoveredCapability:
    metadata = dict(definition.metadata)
    if definition.description:
        metadata.setdefault("description", definition.description)
    if definition.side_effects:
        metadata.setdefault("side_effects", list(definition.side_effects))

    descriptor = CapabilityDescriptor(
        id=definition.id,
        name=definition.name or definition.id,
        version=definition.version,
        owner_agent=definition.owner_agent or _agent_id(agent),
        machine_scope=definition.machine_scope,
        permissions=list(definition.permissions),
        input_schema=dict(definition.input_schema),
        output_schema=dict(definition.output_schema),
        tags=list(definition.tags),
        metadata=metadata,
    )
    provider_handle = _agent_provider_handle(agent, descriptor.id)
    provider_handle["handler_name"] = handler_name
    return DiscoveredCapability(
        descriptor=descriptor,
        provider_handle=provider_handle,
        handler_name=handler_name,
    )


def _agent_provider_handle(agent: Any, capability_id: str) -> dict:
    return {
        "type": "agent",
        "agent_id": _agent_id(agent),
        "capability_id": capability_id,
    }


def _agent_id(agent: Any) -> str:
    descriptor = getattr(agent, "descriptor", agent)
    return getattr(descriptor, "id", "")
