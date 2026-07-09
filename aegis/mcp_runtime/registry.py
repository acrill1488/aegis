from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import MCPServerRecord


DEFAULT_MCP_SERVER_REGISTRY_PATH = Path(r"F:\AI_WORKSPACE\mcp\servers.json")


class MCPServerRegistry:
    """Persistent catalog of external MCP servers known to AEGIS."""

    def __init__(self, path: str | Path = DEFAULT_MCP_SERVER_REGISTRY_PATH):
        self.path = Path(path)
        self._servers: dict[str, MCPServerRecord] = {}
        self._persistence_available = True
        self._ensure_file()
        self._load()

    def add(self, record: MCPServerRecord) -> MCPServerRecord:
        self._validate_record(record)
        self._servers[record.id] = record
        self._save()
        return record

    def get(self, server_id: str) -> MCPServerRecord | None:
        return self._servers.get(server_id)

    def list(self, enabled_only: bool = False) -> list[MCPServerRecord]:
        records = list(self._servers.values())
        if enabled_only:
            records = [record for record in records if record.enabled]
        return records

    def enable(self, server_id: str) -> MCPServerRecord:
        record = self._require_server(server_id)
        record.enabled = True
        self._save()
        return record

    def disable(self, server_id: str) -> MCPServerRecord:
        record = self._require_server(server_id)
        record.enabled = False
        self._save()
        return record

    def remove(self, server_id: str) -> bool:
        if server_id not in self._servers:
            return False
        del self._servers[server_id]
        self._save()
        return True

    def _require_server(self, server_id: str) -> MCPServerRecord:
        record = self.get(server_id)
        if record is None:
            raise KeyError(f"MCP server not found: {server_id}")
        return record

    def _ensure_file(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.write_text("[]", encoding="utf-8")
        except OSError:
            self._persistence_available = False

    def _load(self) -> None:
        if not self._persistence_available:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []

        if isinstance(data, dict):
            items = data.get("servers", data.values())
        elif isinstance(data, list):
            items = data
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                record = self._record_from_plain(item)
            except (KeyError, TypeError, ValueError):
                continue
            self._servers[record.id] = record

        self._save()

    def _save(self) -> None:
        if not self._persistence_available:
            return
        try:
            self.path.write_text(
                json.dumps(
                    to_plain(self.list()),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            self._persistence_available = False

    def _record_from_plain(self, item: dict[str, Any]) -> MCPServerRecord:
        env = item.get("env") or {}
        if not isinstance(env, dict):
            env = {}

        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        return MCPServerRecord(
            id=str(item["id"]),
            name=str(item["name"]),
            command=str(item["command"]),
            args=self._string_list(item.get("args")),
            env={str(key): str(value) for key, value in env.items()},
            enabled=bool(item.get("enabled", True)),
            status=str(item.get("status", "unknown")),
            capabilities=self._string_list(item.get("capabilities")),
            metadata=metadata,
        )

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _validate_record(self, record: MCPServerRecord) -> None:
        if not record.id:
            raise ValueError("MCP server id is required")
        if not record.name:
            raise ValueError("MCP server name is required")
        if not record.command:
            raise ValueError("MCP server command is required")
