from __future__ import annotations

from typing import Any

from aegis.serialization import to_plain

from .models import (
    CapabilityDescriptor,
    CapabilityInvocationRequest,
    CapabilityInvocationResult,
)
from .registry import CapabilityRegistry
from .router import CapabilityRouter


class CapabilityRuntime:
    def __init__(self, core: Any):
        self.core = core
        self.registry = CapabilityRegistry()
        self.router = CapabilityRouter(core, self.registry)

    def register(self, descriptor: CapabilityDescriptor, provider_handle: dict) -> dict:
        registration = self.registry.register(descriptor, provider_handle)
        self._publish(
            "capability.registered",
            descriptor.id,
            {
                "capability": descriptor,
                "provider_handle": provider_handle,
            },
        )
        return registration

    def unregister(
        self,
        capability_id: str,
        provider_handle: dict | None = None,
    ) -> dict | None:
        return self.registry.unregister(capability_id, provider_handle=provider_handle)

    def invoke(
        self,
        request: CapabilityInvocationRequest,
    ) -> CapabilityInvocationResult:
        self._publish(
            "capability.invoked",
            request.capability_id,
            {
                "capability_id": request.capability_id,
                "caller": request.caller,
                "payload": request.payload,
                "timeout_ms": request.timeout_ms,
                "metadata": request.metadata,
            },
            trace_id=request.trace_id,
        )

        route = self.router.resolve(request.capability_id)
        if route is None:
            result = CapabilityInvocationResult(
                success=False,
                capability_id=request.capability_id,
                error=f"Capability unavailable: {request.capability_id}",
            )
            self._publish_result("capability.failed", result, request.trace_id)
            return result

        try:
            result = self.router.invoke(route, request)
        except Exception as exc:
            result = CapabilityInvocationResult(
                success=False,
                capability_id=request.capability_id,
                error=str(exc),
                selected_route=route,
            )

        event_type = "capability.completed" if result.success else "capability.failed"
        self._publish_result(event_type, result, request.trace_id)
        return result

    def resolve(self, capability_id: str) -> dict | None:
        return self.router.resolve(capability_id)

    def list(self) -> list[CapabilityDescriptor]:
        return self.registry.list()

    def find_by_tag(self, tag: str) -> list[CapabilityDescriptor]:
        return self.registry.find_by_tag(tag)

    def register_agent_capabilities(self) -> None:
        agent_runtime = getattr(self.core, "agent_runtime", None)
        if agent_runtime is None:
            return

        for agent in agent_runtime.list():
            for capability in agent.capabilities:
                metadata = dict(capability.metadata)
                descriptor = CapabilityDescriptor(
                    id=capability.id,
                    name=capability.id,
                    version=capability.version,
                    owner_agent=agent.id,
                    machine_scope=metadata.get("machine_scope", "local"),
                    permissions=list(capability.permissions),
                    input_schema=dict(metadata.get("input_schema", {})),
                    output_schema=dict(metadata.get("output_schema", {})),
                    tags=list(metadata.get("tags", [])),
                    metadata={
                        **metadata,
                        "description": capability.description,
                        "side_effects": list(capability.side_effects),
                    },
                )
                self.register(
                    descriptor,
                    {
                        "type": "agent",
                        "agent_id": agent.id,
                        "capability_id": capability.id,
                    },
                )

    def _publish_result(
        self,
        event_type: str,
        result: CapabilityInvocationResult,
        trace_id: str | None = None,
    ) -> None:
        self._publish(
            event_type,
            result.capability_id,
            {"result": result},
            trace_id=trace_id,
        )

    def _publish(
        self,
        event_type: str,
        capability_id: str,
        payload: dict,
        trace_id: str | None = None,
    ) -> None:
        events = getattr(self.core, "events", None)
        if events is None or not hasattr(events, "publish"):
            return
        try:
            events.publish(
                event_type,
                source=f"capability_runtime:{capability_id}",
                payload=to_plain(payload),
                trace_id=trace_id,
            )
        except Exception:
            return
