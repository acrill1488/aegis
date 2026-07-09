from __future__ import annotations

from typing import Any

from aegis.capabilities import CapabilityDescriptor

from .models import MCPServerRecord
from .registry import MCPServerRegistry


class MCPRuntime:
    """MCP provider registry and safe discovery skeleton.

    v1 deliberately does not start MCP transports. It only exposes configured
    MCP servers as external Capability providers.
    """

    def __init__(self, core: Any, registry: MCPServerRegistry | None = None):
        self.core = core
        self.registry = registry or MCPServerRegistry()

    def register_server(self, record: MCPServerRecord) -> MCPServerRecord:
        return self.registry.add(record)

    def list_servers(self) -> list[MCPServerRecord]:
        return self.registry.list()

    def server_status(self, server_id: str) -> str | None:
        record = self.registry.get(server_id)
        if record is None:
            return None
        return record.status

    def auto_discover_enabled(self) -> list[dict]:
        results = []
        for record in self.registry.list(enabled_only=True):
            results.append(self.discover(record.id))
        return results

    def discover(self, server_id: str) -> dict:
        record = self.registry.get(server_id)
        if record is None:
            return {
                "server_id": server_id,
                "status": "not_found",
                "capabilities": [],
                "registered": [],
            }
        if not record.enabled:
            record.status = "disabled"
            self.registry.add(record)
            return {
                "server_id": server_id,
                "status": record.status,
                "capabilities": list(record.capabilities),
                "registered": [],
            }

        registered = []
        capability_runtime = getattr(self.core, "capability_runtime", None)
        if capability_runtime is not None:
            for capability_id in record.capabilities:
                descriptor = CapabilityDescriptor(
                    id=capability_id,
                    name=capability_id,
                    version="1",
                    owner_agent=f"mcp:{record.id}",
                    machine_scope="local",
                    tags=["mcp"],
                    metadata={
                        "provider_type": "mcp",
                        "server_id": record.id,
                        "server_name": record.name,
                    },
                )
                provider_handle = {
                    "type": "mcp",
                    "server_id": record.id,
                    "capability_id": capability_id,
                }
                capability_runtime.register(descriptor, provider_handle)
                registered.append(capability_id)

        record.status = "discovered"
        self.registry.add(record)
        return {
            "server_id": server_id,
            "status": record.status,
            "capabilities": list(record.capabilities),
            "registered": registered,
        }
