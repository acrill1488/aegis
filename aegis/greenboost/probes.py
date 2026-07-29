"""One-shot resource probes built on existing AEGIS status APIs."""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from aegis.embeddings.registry import EmbeddingRegistry
from aegis.image_generation.providers.comfyui import ComfyUIProvider
from aegis.ocr.providers.unlimited import UnlimitedOCRProvider
from aegis.providers.paddleocr import PaddleOCRProvider
from aegis.remote.client import RemoteRuntimeClient
from aegis.remote.config import RemoteRuntimeConfig, load_remote_runtime_config
from aegis.system.api import SystemAPI

from .contracts import (
    CPUState,
    ContractModel,
    DiskState,
    GPUState,
    MemoryState,
    ModelResourceState,
    NodeReference,
    NodeScope,
    ProbeWarning,
    ResourceSnapshot,
    ServiceResourceState,
)


class ProbeResult(ContractModel):
    """Immutable ResourceSnapshot-compatible fragment returned by a probe."""

    cpu: CPUState | None = None
    ram: MemoryState | None = None
    gpus: tuple[GPUState, ...] = ()
    disk: DiskState | None = None
    services: tuple[ServiceResourceState, ...] = ()
    models: tuple[ModelResourceState, ...] = ()
    warnings: tuple[ProbeWarning, ...] = Field(default=(), alias="probe_warnings")

    model_config = {**ContractModel.model_config, "populate_by_name": True}


def _warning(code: str, exc: Exception, resource: str) -> ProbeWarning:
    message = str(exc).strip() or type(exc).__name__
    return ProbeWarning(code=code, message=message[:2048], resource=resource)


class HostProbe:
    """Observe local CPU, RAM, and disk through the existing SystemAPI."""

    def __init__(self, system: SystemAPI | None = None) -> None:
        self.system = system or SystemAPI()

    def probe(self) -> ProbeResult:
        warnings: list[ProbeWarning] = []
        cpu = None
        ram = None
        disk = None
        try:
            value = self.system.cpu()
            cpu = CPUState(
                logical_cores=value.logical_cores,
                available_cores=max(0.0, value.logical_cores * (100.0 - value.percent) / 100.0),
                utilization_percent=value.percent,
            )
        except Exception as exc:
            warnings.append(_warning("host.cpu.unavailable", exc, "cpu"))
        try:
            value = self.system.memory()
            ram = MemoryState(
                total_mb=round(value.total_gb * 1024),
                used_mb=round(value.used_gb * 1024),
                available_mb=round(value.free_gb * 1024),
            )
        except Exception as exc:
            warnings.append(_warning("host.ram.unavailable", exc, "ram"))
        try:
            values = self.system.storage()
            disk = DiskState(
                total_mb=round(sum(item.total_gb for item in values) * 1024),
                used_mb=round(sum(item.used_gb for item in values) * 1024),
                available_mb=round(sum(item.free_gb for item in values) * 1024),
            )
        except Exception as exc:
            warnings.append(_warning("host.disk.unavailable", exc, "disk"))
        return ProbeResult(cpu=cpu, ram=ram, disk=disk, probe_warnings=tuple(warnings))


class GPUProbe:
    """Observe GPUs through the existing SystemAPI nvidia-smi adapter."""

    def __init__(self, system: SystemAPI | None = None) -> None:
        self.system = system or SystemAPI()

    def probe(self) -> ProbeResult:
        try:
            values = self.system.gpu()
            gpus = tuple(
                GPUState(
                    id=str(index),
                    name=value.name,
                    utilization_percent=value.load_percent,
                    temperature_celsius=value.temperature_c,
                    vram=MemoryState(
                        total_mb=round(value.memory_total_mb) if value.memory_total_mb is not None else None,
                        used_mb=round(value.memory_used_mb) if value.memory_used_mb is not None else None,
                        available_mb=round(value.memory_free_mb) if value.memory_free_mb is not None else None,
                    ),
                )
                for index, value in enumerate(values)
            )
            return ProbeResult(gpus=gpus)
        except Exception as exc:
            return ProbeResult(probe_warnings=(_warning("gpu.unavailable", exc, "gpu"),))


class DockerProbe:
    """Adapt the canonical SystemAPI Docker status."""

    def __init__(self, system: SystemAPI | None = None) -> None:
        self.system = system or SystemAPI()

    def probe(self) -> ProbeResult:
        try:
            value = self.system.docker()
            return ProbeResult(services=(ServiceResourceState(
                id="docker", state="available" if value.available else "unavailable",
                reachable=value.available,
            ),))
        except Exception as exc:
            return ProbeResult(
                services=(ServiceResourceState(id="docker", state="unknown", reachable=False),),
                probe_warnings=(_warning("docker.probe.failed", exc, "docker"),),
            )


class OllamaProbe:
    """Adapt the canonical SystemAPI Ollama /api/tags status."""

    def __init__(self, system: SystemAPI | None = None) -> None:
        self.system = system or SystemAPI()

    def probe(self) -> ProbeResult:
        try:
            value = self.system.ollama()
            return ProbeResult(services=(ServiceResourceState(
                id="ollama", state="available" if value.available else "unavailable",
                reachable=value.available,
            ),))
        except Exception as exc:
            return ProbeResult(
                services=(ServiceResourceState(id="ollama", state="unknown", reachable=False),),
                probe_warnings=(_warning("ollama.probe.failed", exc, "ollama"),),
            )


class OCRProbe:
    """Adapt the existing health APIs of production OCR providers."""

    def __init__(self, providers: Iterable[Any] | Any | None = None) -> None:
        if providers is None:
            providers = (UnlimitedOCRProvider(), PaddleOCRProvider())
        elif not isinstance(providers, Iterable) or isinstance(providers, (str, bytes)):
            providers = (providers,)
        self.providers = tuple(providers)

    def probe(self) -> ProbeResult:
        services: list[ServiceResourceState] = []
        models: list[ModelResourceState] = []
        warnings: list[ProbeWarning] = []
        for provider in self.providers:
            name_value = getattr(provider, "name", type(provider).__name__)
            provider_name = str(name_value() if callable(name_value) else name_value)
            service_id = "unlimited-ocr" if provider_name == "unlimited" else provider_name
            try:
                health = provider.health()
                info_method = getattr(provider, "info", None)
                info = info_method() if callable(info_method) else {}
                reachable = bool(health.get(
                    "service_alive", health.get("service_reachable", health.get("available", False))
                ))
                if provider_name != "unlimited" and "available" not in health:
                    reachable = str(health.get("status", "")).lower() in {"ok", "ready", "healthy"}
                model_id = info.get("model_id") or health.get("model_id")
                loaded = health.get("model_loaded", info.get("model_loaded"))
                warm = health.get("inference_ready", info.get("inference_ready"))
                services.append(ServiceResourceState(
                    id=service_id, state=str(health.get("status") or "unknown"), reachable=reachable,
                ))
                if model_id:
                    models.append(ModelResourceState(
                        id=str(model_id), provider=service_id, loaded=loaded, warm=warm,
                    ))
            except Exception as exc:
                services.append(ServiceResourceState(id=service_id, state="unknown", reachable=False))
                warnings.append(_warning("ocr.probe.failed", exc, service_id))
        return ProbeResult(
            services=tuple(services), models=tuple(models), probe_warnings=tuple(warnings),
        )


class ComfyUIProbe:
    """Adapt the existing ComfyUI availability check."""

    def __init__(self, provider: ComfyUIProvider | None = None) -> None:
        self.provider = provider or ComfyUIProvider()

    def probe(self) -> ProbeResult:
        try:
            available = self.provider.available()
            return ProbeResult(services=(ServiceResourceState(
                id="comfyui", state="available" if available else "unavailable",
                reachable=available,
            ),))
        except Exception as exc:
            return ProbeResult(
                services=(ServiceResourceState(id="comfyui", state="unknown", reachable=False),),
                probe_warnings=(_warning("comfyui.probe.failed", exc, "comfyui"),),
            )


class EmbeddingProbe:
    """Adapt registered embedding providers' health APIs."""

    def __init__(self, registry: EmbeddingRegistry | None = None) -> None:
        self.registry = registry or EmbeddingRegistry()

    def probe(self) -> ProbeResult:
        services: list[ServiceResourceState] = []
        models: list[ModelResourceState] = []
        warnings: list[ProbeWarning] = []
        for provider in self.registry.list():
            provider_id = str(provider.id)
            try:
                health = provider.health()
                services.append(ServiceResourceState(
                    id=provider_id, state=str(health.status), reachable=bool(health.available),
                ))
                models.append(ModelResourceState(
                    id=str(getattr(health, "provider", provider_id)), provider=provider_id,
                    loaded=health.model_loaded, warm=bool(health.available and health.model_loaded),
                ))
            except Exception as exc:
                services.append(ServiceResourceState(id=provider_id, state="unknown", reachable=False))
                warnings.append(_warning("embedding.probe.failed", exc, provider_id))
        return ProbeResult(services=tuple(services), models=tuple(models), probe_warnings=tuple(warnings))


class RemoteProbe:
    """Adapt every configured remote runtime's versioned health API."""

    def __init__(
        self,
        config: RemoteRuntimeConfig | None = None,
        client_factory: Callable[..., RemoteRuntimeClient] = RemoteRuntimeClient,
    ) -> None:
        self.config = config or load_remote_runtime_config()
        self.client_factory = client_factory

    def probe(self) -> ProbeResult:
        services: list[ServiceResourceState] = []
        warnings: list[ProbeWarning] = []
        for node_id, node in sorted(self.config.nodes.items()):
            resource = f"remote-runtime:{node_id}"
            if not self.config.enabled or not node.enabled:
                services.append(ServiceResourceState(id=resource, state="disabled", reachable=False))
                continue
            try:
                client = self.client_factory(
                    node, connect_timeout=self.config.connect_timeout_seconds,
                    read_timeout=self.config.read_timeout_seconds,
                )
                health = client.health()
                state = str(health.get("status") or "unknown")
                services.append(ServiceResourceState(
                    id=resource, state=state, reachable=state in {"ok", "ready", "healthy"},
                ))
            except Exception as exc:
                services.append(ServiceResourceState(id=resource, state="unreachable", reachable=False))
                warnings.append(_warning("remote.probe.failed", exc, resource))
        return ProbeResult(services=tuple(services), probe_warnings=tuple(warnings))


class ResourceProbe:
    """Merge one synchronous pass of all resource probes into one snapshot."""

    def __init__(
        self,
        probes: Iterable[Any] | None = None,
        *,
        node: NodeReference | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.probes = tuple(probes) if probes is not None else (
            HostProbe(), GPUProbe(), DockerProbe(), OllamaProbe(), OCRProbe(),
            ComfyUIProbe(), EmbeddingProbe(), RemoteProbe(),
        )
        self.node = node or NodeReference(id=socket.gethostname(), scope=NodeScope.local)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def probe(self) -> ResourceSnapshot:
        cpu = CPUState()
        ram = MemoryState()
        disk = DiskState()
        gpus: list[GPUState] = []
        services: list[ServiceResourceState] = []
        models: list[ModelResourceState] = []
        warnings: list[ProbeWarning] = []
        for probe in self.probes:
            try:
                result = probe.probe()
            except Exception as exc:
                warnings.append(_warning("resource.probe.failed", exc, type(probe).__name__))
                continue
            if result.cpu is not None:
                cpu = result.cpu
            if result.ram is not None:
                ram = result.ram
            if result.disk is not None:
                disk = result.disk
            gpus.extend(result.gpus)
            services.extend(result.services)
            models.extend(result.models)
            warnings.extend(result.warnings)
        return ResourceSnapshot(
            timestamp=self.clock(), node=self.node, cpu=cpu, ram=ram, gpus=tuple(gpus),
            disk=disk, services=tuple(services), models=tuple(models),
            probe_warnings=tuple(warnings),
        )
