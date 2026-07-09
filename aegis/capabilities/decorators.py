from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar, overload


CapabilityCallable = TypeVar("CapabilityCallable", bound=Callable[..., Any])


@dataclass(frozen=True)
class CapabilityDefinition:
    id: str
    name: str | None = None
    version: str = "1"
    owner_agent: str | None = None
    machine_scope: str = "local"
    permissions: list[str] = field(default_factory=list)
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    description: str = ""
    side_effects: list[str] = field(default_factory=list)


@overload
def capability(func: CapabilityCallable, /) -> CapabilityCallable:
    ...


@overload
def capability(
    capability_id: str | None = None,
    /,
    *,
    id: str | None = None,
    name: str | None = None,
    version: str = "1",
    owner_agent: str | None = None,
    machine_scope: str = "local",
    permissions: list[str] | tuple[str, ...] | None = None,
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    metadata: dict | None = None,
    description: str = "",
    side_effects: list[str] | tuple[str, ...] | None = None,
) -> Callable[[CapabilityCallable], CapabilityCallable]:
    ...


def capability(
    capability_id: str | CapabilityCallable | None = None,
    /,
    *,
    id: str | None = None,
    name: str | None = None,
    version: str = "1",
    owner_agent: str | None = None,
    machine_scope: str = "local",
    permissions: list[str] | tuple[str, ...] | None = None,
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    metadata: dict | None = None,
    description: str = "",
    side_effects: list[str] | tuple[str, ...] | None = None,
) -> CapabilityCallable | Callable[[CapabilityCallable], CapabilityCallable]:
    """Mark an agent method as a Capability SDK declaration."""
    if callable(capability_id):
        func = capability_id
        definition = CapabilityDefinition(id=_default_capability_id(func))
        setattr(func, "__aegis_capability__", definition)
        return func

    resolved_id = id or capability_id
    if not resolved_id:
        raise ValueError("Capability id is required")

    definition = CapabilityDefinition(
        id=resolved_id,
        name=name,
        version=version,
        owner_agent=owner_agent,
        machine_scope=machine_scope,
        permissions=list(permissions or []),
        input_schema=dict(input_schema or {}),
        output_schema=dict(output_schema or {}),
        tags=list(tags or []),
        metadata=dict(metadata or {}),
        description=description,
        side_effects=list(side_effects or []),
    )

    def decorate(func: CapabilityCallable) -> CapabilityCallable:
        setattr(func, "__aegis_capability__", definition)
        return func

    return decorate


def _default_capability_id(func: Callable[..., Any]) -> str:
    return func.__name__.replace("_", ".")
