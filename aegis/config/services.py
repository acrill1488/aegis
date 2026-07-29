"""Centralized network service configuration for AEGIS."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

DEFAULT_CONFIG_PATH = Path(r"F:\AI_WORKSPACE\config\services.yaml")
SUPPORTED_SERVICES = {"ollama", "unlimited_ocr", "comfyui"}
DEFAULT_PORTS = {"ollama": 11434, "unlimited_ocr": 8190, "comfyui": 8188}


class ServicesConfigError(ValueError):
    """Raised when the services configuration is present but invalid."""


@dataclass(frozen=True)
class ResolvedValue:
    value: str
    source: str


@dataclass(frozen=True)
class ServicesConfig:
    path: Path
    data: dict[str, Any]
    configuration_source: str


class GreenBoostConfig(BaseModel):
    """Validated GBIP client settings from the central AEGIS configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    base_url: HttpUrl = "http://127.0.0.1:8091"
    api_key: str | None = None
    connect_timeout: float = Field(default=5.0, gt=0)
    read_timeout: float = Field(default=30.0, gt=0)
    write_timeout: float = Field(default=30.0, gt=0)
    pool_timeout: float = Field(default=5.0, gt=0)
    retries: int = Field(default=0, ge=0, le=10)
    server: "GreenBoostServerConfig" = Field(
        default_factory=lambda: GreenBoostServerConfig()
    )
    probes: "GreenBoostProbesConfig" = Field(
        default_factory=lambda: GreenBoostProbesConfig()
    )


class ProbeToggle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True


class GreenBoostServerConfig(BaseModel):
    """GBIP service settings; the bearer token is resolved only from the environment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    node_id: str = Field(default="ubuntu-primary", min_length=1, max_length=128)
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8091, ge=1, le=65535)
    token_env: str = Field(default="AEGIS_GREENBOOST_API_KEY", min_length=1)


class TimedProbeToggle(ProbeToggle):
    timeout_seconds: float = Field(default=2.0, gt=0)


class GreenBoostProbesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    local_system: ProbeToggle = Field(default_factory=ProbeToggle)
    nvidia: ProbeToggle = Field(default_factory=ProbeToggle)
    services: TimedProbeToggle = Field(default_factory=TimedProbeToggle)
    models: TimedProbeToggle = Field(
        default_factory=lambda: TimedProbeToggle(timeout_seconds=3.0)
    )
    remote: ProbeToggle = Field(default_factory=ProbeToggle)
    fail_on_required_probe_error: bool = False


def get_greenboost_config() -> GreenBoostConfig:
    """Resolve GBIP settings through the existing services configuration."""

    loaded = load_services_config()
    raw = dict(loaded.data.get("greenboost") or {})
    environment = {
        "base_url": os.getenv("AEGIS_GREENBOOST_BASE_URL"),
        "api_key": os.getenv("AEGIS_GREENBOOST_API_KEY"),
    }
    raw.update({key: value for key, value in environment.items() if value is not None})
    try:
        return GreenBoostConfig.model_validate(raw)
    except ValidationError as exc:
        raise _error(loaded.path, f"greenboost is invalid: {exc}") from exc


def get_services_config_path() -> Path:
    return Path(os.environ.get("AEGIS_SERVICES_CONFIG", DEFAULT_CONFIG_PATH))


def _error(path: Path, message: str) -> ServicesConfigError:
    return ServicesConfigError(
        f"Invalid AEGIS services configuration:\n{path}\n\n{message}"
    )


def _validate_url(value: Any, field: str, path: Path) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _error(path, f"{field} must be a non-empty HTTP or HTTPS URL.")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise _error(path, f"{field} must be a valid HTTP or HTTPS URL.")
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise _error(path, f"{field} contains an invalid port.") from exc
    if parsed_port is not None and not 1 <= parsed_port <= 65535:
        raise _error(path, f"{field} contains an invalid port.")
    return value.rstrip("/")


def load_services_config(config_path: str | Path | None = None) -> ServicesConfig:
    path = Path(config_path) if config_path is not None else get_services_config_path()
    if not path.exists():
        data = {
            "schema_version": 1,
            "server": {"host": "127.0.0.1", "scheme": "http"},
            "services": {
                name: {"port": port, "base_url": None}
                for name, port in DEFAULT_PORTS.items()
            },
            "paths": {},
            "ocr": {"providers": {"paddleocr": {}}},
            "embeddings": {
                "default_provider": "bge-m3",
                "max_texts_per_request": 256,
                "providers": {"bge-m3": {}},
            },
            "remote_runtime": {
                "enabled": True,
                "client": {
                    "default_node": "ubuntu-primary",
                    "connect_timeout_seconds": 5,
                    "read_timeout_seconds": 300,
                },
                "nodes": {},
                "server": {
                    "enabled": False,
                    "node_id": "ubuntu-primary",
                    "host": "127.0.0.1",
                    "port": 8090,
                },
            },
        }
        return ServicesConfig(path, data, "fallback")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as exc:
        raise _error(path, f"YAML could not be loaded: {exc}") from exc
    if not isinstance(data, dict):
        raise _error(path, "The YAML root must be a mapping.")
    if data.get("schema_version") != 1:
        raise _error(path, "schema_version must be 1.")
    server = data.get("server")
    services = data.get("services")
    paths = data.get("paths", {})
    if (
        not isinstance(server, dict)
        or not isinstance(services, dict)
        or not isinstance(paths, dict)
    ):
        raise _error(path, "server, services, and paths must be mappings.")
    scheme = server.get("scheme")
    host = server.get("host")
    if scheme not in {"http", "https"}:
        raise _error(path, "server.scheme must be http or https.")
    if not isinstance(host, str) or not host.strip():
        raise _error(path, "server.host must be a non-empty string.")
    for name, service in services.items():
        if name not in SUPPORTED_SERVICES:
            raise _error(path, f"services.{name} is not a known service.")
        if not isinstance(service, dict):
            raise _error(path, f"services.{name} must be a mapping.")
        port = service.get("port")
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            raise _error(
                path, f"services.{name}.port must be an integer between 1 and 65535."
            )
        _validate_url(service.get("base_url"), f"services.{name}.base_url", path)
    missing = SUPPORTED_SERVICES - services.keys()
    if missing:
        raise _error(path, f"Missing services: {', '.join(sorted(missing))}.")
    if any(not isinstance(value, str) or not value for value in paths.values()):
        raise _error(path, "All paths values must be non-empty strings.")
    ocr = data.get("ocr", {})
    if not isinstance(ocr, dict) or not isinstance(ocr.get("providers", {}), dict):
        raise _error(path, "ocr and ocr.providers must be mappings when present.")
    embeddings = data.get("embeddings", {})
    if not isinstance(embeddings, dict) or not isinstance(
        embeddings.get("providers", {}), dict
    ):
        raise _error(
            path, "embeddings and embeddings.providers must be mappings when present."
        )
    execution = embeddings.get("execution", "local")
    if execution not in {"local", "remote", "auto"}:
        raise _error(path, "embeddings.execution must be local, remote, or auto.")
    remote_runtime = data.get("remote_runtime", {})
    if not isinstance(remote_runtime, dict):
        raise _error(path, "remote_runtime must be a mapping when present.")
    try:
        GreenBoostConfig.model_validate(data.get("greenboost") or {})
    except ValidationError as exc:
        raise _error(path, f"greenboost is invalid: {exc}") from exc
    return ServicesConfig(path, data, "yaml")


def resolve_server_host(*, explicit: str | None = None) -> ResolvedValue:
    if explicit:
        return ResolvedValue(explicit, "explicit override")
    if value := os.environ.get("AEGIS_SERVER_HOST"):
        return ResolvedValue(value, "environment")
    config = load_services_config()
    return ResolvedValue(
        str(config.data["server"]["host"]), config.configuration_source
    )


def get_server_host() -> str:
    return resolve_server_host().value


def resolve_service_base_url(
    name: str, *, explicit: str | None = None
) -> ResolvedValue:
    if name not in SUPPORTED_SERVICES:
        raise KeyError(f"Unknown AEGIS service: {name}")
    path = get_services_config_path()
    if explicit:
        return ResolvedValue(
            _validate_url(explicit, "explicit base_url", path) or "",
            "explicit override",
        )
    env_name = f"AEGIS_{name.upper()}_BASE_URL"
    if value := os.environ.get(env_name):
        return ResolvedValue(_validate_url(value, env_name, path) or "", "environment")
    config = load_services_config()
    service = config.data["services"][name]
    if service.get("base_url"):
        return ResolvedValue(
            str(service["base_url"]).rstrip("/"), config.configuration_source
        )
    scheme = os.environ.get("AEGIS_SERVER_SCHEME", str(config.data["server"]["scheme"]))
    if scheme not in {"http", "https"}:
        raise _error(config.path, "AEGIS_SERVER_SCHEME must be http or https.")
    host = os.environ.get("AEGIS_SERVER_HOST", str(config.data["server"]["host"]))
    source = (
        "environment"
        if "AEGIS_SERVER_SCHEME" in os.environ or "AEGIS_SERVER_HOST" in os.environ
        else config.configuration_source
    )
    return ResolvedValue(f"{scheme}://{host}:{service['port']}", source)


def get_service_base_url(name: str, explicit: str | None = None) -> str:
    return resolve_service_base_url(name, explicit=explicit).value


def resolve_configured_path(
    name: str, *, explicit: str | Path | None = None
) -> ResolvedValue:
    if explicit is not None:
        return ResolvedValue(str(explicit), "explicit override")
    env_name = f"AEGIS_{name.upper()}_PATH"
    if value := os.environ.get(env_name):
        return ResolvedValue(value, "environment")
    config = load_services_config()
    value = config.data["paths"].get(name)
    if value:
        return ResolvedValue(str(value), config.configuration_source)
    if config.configuration_source == "fallback" and name == "comfyui_models":
        return ResolvedValue(str(Path(r"F:\AI_WORKSPACE\models\image")), "fallback")
    raise KeyError(f"Unknown or unconfigured AEGIS path: {name}")


def get_configured_path(name: str, explicit: str | Path | None = None) -> str:
    return resolve_configured_path(name, explicit=explicit).value
