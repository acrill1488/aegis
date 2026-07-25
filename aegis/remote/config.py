"""Remote runtime configuration from the central services.yaml layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aegis.config.services import load_services_config


@dataclass(frozen=True)
class RemoteNodeConfig:
    id: str
    base_url: str
    token_env: str = "AEGIS_REMOTE_TOKEN"
    enabled: bool = True

    @property
    def token(self) -> str | None:
        return os.environ.get(self.token_env)


@dataclass(frozen=True)
class RemoteRuntimeConfig:
    enabled: bool
    default_node: str
    nodes: dict[str, RemoteNodeConfig]
    connect_timeout_seconds: float
    read_timeout_seconds: float
    server: dict[str, Any]

    def node(self, node_id: str | None = None) -> RemoteNodeConfig:
        selected = node_id or self.default_node
        if selected not in self.nodes:
            raise ValueError(f"Remote runtime node is not configured: {selected}")
        return self.nodes[selected]


def load_remote_runtime_config(config_path: str | Path | None = None) -> RemoteRuntimeConfig:
    data = load_services_config(config_path).data.get("remote_runtime", {})
    if not isinstance(data, dict):
        raise ValueError("remote_runtime must be a mapping")
    client = data.get("client", {})
    nodes_data = data.get("nodes", {})
    server = data.get("server", {})
    if not isinstance(client, dict) or not isinstance(nodes_data, dict) or not isinstance(server, dict):
        raise ValueError("remote_runtime.client, nodes and server must be mappings")
    default_node = str(client.get("default_node", "ubuntu-primary"))
    nodes: dict[str, RemoteNodeConfig] = {}
    for node_id, value in nodes_data.items():
        if not isinstance(value, dict):
            raise ValueError(f"remote_runtime.nodes.{node_id} must be a mapping")
        base_url = value.get("base_url")
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            raise ValueError(f"remote_runtime.nodes.{node_id}.base_url must be an HTTP URL")
        nodes[str(node_id)] = RemoteNodeConfig(
            id=str(node_id), base_url=base_url.rstrip("/"),
            token_env=str(value.get("token_env", "AEGIS_REMOTE_TOKEN")),
            enabled=bool(value.get("enabled", True)),
        )
    return RemoteRuntimeConfig(
        enabled=bool(data.get("enabled", True)), default_node=default_node, nodes=nodes,
        connect_timeout_seconds=float(client.get("connect_timeout_seconds", 5)),
        read_timeout_seconds=float(client.get("read_timeout_seconds", 300)), server=dict(server),
    )


def load_embedding_execution(config_path: str | Path | None = None) -> tuple[str, str | None]:
    section = load_services_config(config_path).data.get("embeddings", {})
    if not isinstance(section, dict):
        raise ValueError("embeddings must be a mapping")
    execution = str(section.get("execution", "local"))
    if execution not in {"local", "remote", "auto"}:
        raise ValueError("embeddings.execution must be one of: local, remote, auto")
    node = section.get("remote_node")
    return execution, str(node) if node is not None else None

