from __future__ import annotations

from typing import Any

from aegis.agents.runtime import AgentInvocation
from aegis.serialization import to_plain

from .models import CapabilityInvocationRequest, CapabilityInvocationResult


class CapabilityRouter:
    def __init__(self, core: Any, registry):
        self.core = core
        self.registry = registry

    def resolve(self, capability_id: str) -> dict | None:
        record = self.registry.resolve(capability_id)
        if record is None:
            return None

        provider_handles = record["provider_handles"]
        if not provider_handles:
            return None

        descriptor = record["descriptor"]
        provider_handle = provider_handles[0]
        return {
            "capability_id": descriptor.id,
            "provider_type": provider_handle.get("type"),
            "provider_handle": provider_handle,
            "owner_agent": descriptor.owner_agent,
            "machine_scope": descriptor.machine_scope,
            "metadata": dict(descriptor.metadata),
        }

    def invoke(
        self,
        route: dict,
        request: CapabilityInvocationRequest,
    ) -> CapabilityInvocationResult:
        provider_handle = route.get("provider_handle") or {}
        provider_type = provider_handle.get("type")

        if provider_type == "agent":
            return self._invoke_agent(route, provider_handle, request)
        if provider_type == "runtime":
            return self._invoke_runtime(route, provider_handle, request)

        return CapabilityInvocationResult(
            success=False,
            capability_id=request.capability_id,
            error=f"Unsupported capability provider type: {provider_type}",
            selected_route=route,
        )

    def _invoke_agent(
        self,
        route: dict,
        provider_handle: dict,
        request: CapabilityInvocationRequest,
    ) -> CapabilityInvocationResult:
        agent_id = provider_handle.get("agent_id")
        agent_capability_id = provider_handle.get("capability_id") or request.capability_id
        if not agent_id:
            return CapabilityInvocationResult(
                success=False,
                capability_id=request.capability_id,
                error="Agent provider handle is missing agent_id",
                selected_route=route,
            )

        agent_result = self.core.agent_runtime.invoke(
            agent_id,
            AgentInvocation(
                capability_id=agent_capability_id,
                payload=request.payload,
                trace_id=request.trace_id,
            ),
        )
        return CapabilityInvocationResult(
            success=agent_result.success,
            capability_id=request.capability_id,
            output=to_plain(agent_result.output),
            error=agent_result.error,
            selected_route=to_plain(route),
            metadata=to_plain(agent_result.metadata),
        )

    def _invoke_runtime(
        self,
        route: dict,
        provider_handle: dict,
        request: CapabilityInvocationRequest,
    ) -> CapabilityInvocationResult:
        runtime_name = provider_handle.get("runtime")
        method_name = provider_handle.get("method")
        if not runtime_name or not method_name:
            return CapabilityInvocationResult(
                success=False,
                capability_id=request.capability_id,
                error="Runtime provider handle is missing runtime or method",
                selected_route=route,
            )

        runtime = self.core.registry.get(runtime_name)
        if runtime is None:
            return CapabilityInvocationResult(
                success=False,
                capability_id=request.capability_id,
                error=f"Runtime not found: {runtime_name}",
                selected_route=route,
            )

        handler = getattr(runtime, str(method_name), None)
        if not callable(handler):
            return CapabilityInvocationResult(
                success=False,
                capability_id=request.capability_id,
                error=f"Runtime method not found: {runtime_name}.{method_name}",
                selected_route=route,
            )

        output = handler(request.payload)
        return CapabilityInvocationResult(
            success=True,
            capability_id=request.capability_id,
            output=to_plain(output),
            selected_route=to_plain(route),
        )
