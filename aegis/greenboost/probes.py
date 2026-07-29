"""One-shot, read-only resource observation built on existing AEGIS APIs."""

from __future__ import annotations

import socket
import importlib
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol

from pydantic import Field

from aegis.config.services import GreenBoostConfig, get_greenboost_config
from aegis.embeddings.registry import EmbeddingRegistry
from aegis.greenboost.client import GreenBoostClient
from aegis.greenboost.errors import (
    AuthenticationError,
    GreenBoostError,
    NodeUnavailable,
    ProtocolError,
    TimeoutError,
)
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


class ProbeStatus(StrEnum):
    success = "success"
    partial = "partial"
    unavailable = "unavailable"
    failed = "failed"
    disabled = "disabled"
    unsupported = "unsupported"


class ProbeResult(ContractModel):
    """Internal ResourceSnapshot-compatible result for one observation source."""

    probe_name: str = "unknown"
    status: ProbeStatus = ProbeStatus.success
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cpu: CPUState | None = None
    ram: MemoryState | None = None
    gpus: tuple[GPUState, ...] = ()
    disk: DiskState | None = None
    services: tuple[ServiceResourceState, ...] = ()
    models: tuple[ModelResourceState, ...] = ()
    remote_snapshot: ResourceSnapshot | None = None
    warnings: tuple[ProbeWarning, ...] = Field(default=(), alias="probe_warnings")
    error_code: str | None = None

    model_config = {**ContractModel.model_config, "populate_by_name": True}


class ResourceProbeProtocol(Protocol):
    @property
    def name(self) -> str: ...

    def collect(self) -> ProbeResult: ...


def _warning(code: str, value: Exception | str, resource: str) -> ProbeWarning:
    message = str(value).strip() or type(value).__name__
    return ProbeWarning(code=code, message=message[:2048], resource=resource)


def _status(warnings: list[ProbeWarning], *, has_data: bool = True) -> ProbeStatus:
    if warnings:
        return ProbeStatus.partial if has_data else ProbeStatus.unavailable
    return ProbeStatus.success


class HostProbe:
    """Observe local CPU, RAM, and disks through the canonical SystemAPI."""

    name = "local-system"

    def __init__(self, system: SystemAPI | None = None) -> None:
        self.system = system or SystemAPI()

    def collect(self) -> ProbeResult:
        warnings: list[ProbeWarning] = []
        cpu = ram = disk = None
        try:
            cpu_value = self.system.cpu()
            cpu = CPUState(
                logical_cores=cpu_value.logical_cores,
                available_cores=max(
                    0.0, cpu_value.logical_cores * (100.0 - cpu_value.percent) / 100.0
                ),
                utilization_percent=cpu_value.percent,
            )
        except Exception as exc:
            warnings.append(_warning("host.cpu.unavailable", exc, "cpu"))
        try:
            memory_value = self.system.memory()
            ram = MemoryState(
                total_mb=round(memory_value.total_gb * 1024),
                used_mb=round(memory_value.used_gb * 1024),
                available_mb=round(memory_value.free_gb * 1024),
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
        has_data = any(value is not None for value in (cpu, ram, disk))
        return ProbeResult(
            probe_name=self.name,
            status=_status(warnings, has_data=has_data),
            cpu=cpu,
            ram=ram,
            disk=disk,
            probe_warnings=tuple(warnings),
        )

    probe = collect


LocalSystemProbe = HostProbe


class NvidiaGpuProbe:
    """Observe NVIDIA devices through the optional official NVML bindings."""

    name = "nvidia"

    def __init__(self, nvml: Any | None = None) -> None:
        self._nvml = nvml

    def collect(self) -> ProbeResult:
        try:
            nvml: Any = self._nvml
            if nvml is None:
                nvml = importlib.import_module("pynvml")
        except ImportError as exc:
            warning = _warning("nvidia.nvml.unsupported", exc, "nvidia")
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.unsupported,
                probe_warnings=(warning,),
                error_code=warning.code,
            )
        gpus: list[GPUState] = []
        warnings: list[ProbeWarning] = []
        initialized = False
        try:
            nvml.nvmlInit()
            initialized = True
            count = nvml.nvmlDeviceGetCount()
            if count == 0:
                return ProbeResult(
                    probe_name=self.name,
                    status=ProbeStatus.unavailable,
                    error_code="nvidia.device.unavailable",
                )
            for index in range(count):
                try:
                    handle = nvml.nvmlDeviceGetHandleByIndex(index)
                    memory = nvml.nvmlDeviceGetMemoryInfo(handle)
                    utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
                    try:
                        temperature = float(
                            nvml.nvmlDeviceGetTemperature(
                                handle, nvml.NVML_TEMPERATURE_GPU
                            )
                        )
                    except Exception:
                        temperature = None
                    gpus.append(
                        GPUState(
                            id=str(nvml.nvmlDeviceGetUUID(handle)),
                            name=str(nvml.nvmlDeviceGetName(handle)),
                            utilization_percent=float(utilization.gpu),
                            temperature_celsius=temperature,
                            vram=MemoryState(
                                total_mb=round(memory.total / 1024**2),
                                used_mb=round(memory.used / 1024**2),
                                available_mb=round(memory.free / 1024**2),
                            ),
                        )
                    )
                except Exception as exc:
                    warnings.append(
                        _warning("nvidia.device.partial", exc, f"nvidia:{index}")
                    )
        except Exception as exc:
            warning = _warning("nvidia.nvml.unavailable", exc, "nvidia")
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.unavailable,
                probe_warnings=(warning,),
                error_code=warning.code,
            )
        finally:
            if initialized:
                try:
                    nvml.nvmlShutdown()
                except Exception:
                    pass
        gpus.sort(key=lambda gpu: (gpu.id or "", gpu.name or ""))
        return ProbeResult(
            probe_name=self.name,
            status=_status(warnings, has_data=bool(gpus)),
            gpus=tuple(gpus),
            probe_warnings=tuple(warnings),
        )

    probe = collect


class GPUProbe:
    """Compatibility adapter over the existing nvidia-smi-backed SystemAPI."""

    name = "gpu"

    def __init__(self, system: SystemAPI | None = None) -> None:
        self.system = system or SystemAPI()

    def collect(self) -> ProbeResult:
        try:
            values = self.system.gpu()
            gpus = tuple(
                GPUState(
                    id=str(index),
                    name=value.name,
                    utilization_percent=value.load_percent,
                    temperature_celsius=value.temperature_c,
                    vram=MemoryState(
                        total_mb=round(value.memory_total_mb)
                        if value.memory_total_mb is not None
                        else None,
                        used_mb=round(value.memory_used_mb)
                        if value.memory_used_mb is not None
                        else None,
                        available_mb=round(value.memory_free_mb)
                        if value.memory_free_mb is not None
                        else None,
                    ),
                )
                for index, value in enumerate(values)
            )
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.success if gpus else ProbeStatus.unavailable,
                gpus=gpus,
            )
        except Exception as exc:
            warning = _warning("gpu.unavailable", exc, "gpu")
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.unavailable,
                probe_warnings=(warning,),
                error_code=warning.code,
            )

    probe = collect


class _SystemServiceProbe:
    method = ""
    name = ""

    def __init__(self, system: SystemAPI | None = None) -> None:
        self.system = system or SystemAPI()

    def collect(self) -> ProbeResult:
        try:
            value = getattr(self.system, self.method)()
            state = "available" if value.available else "unavailable"
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.success
                if value.available
                else ProbeStatus.unavailable,
                services=(
                    ServiceResourceState(
                        id=self.name, state=state, reachable=value.available
                    ),
                ),
            )
        except Exception as exc:
            warning = _warning(f"{self.name}.probe.failed", exc, self.name)
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.failed,
                services=(
                    ServiceResourceState(
                        id=self.name, state="unknown", reachable=False
                    ),
                ),
                probe_warnings=(warning,),
                error_code=warning.code,
            )

    probe = collect


class DockerProbe(_SystemServiceProbe):
    method = "docker"
    name = "docker"


class OllamaProbe(_SystemServiceProbe):
    method = "ollama"
    name = "ollama"


class OllamaModelProbe:
    """Adapt Ollama's existing tag health surface into canonical model states."""

    name = "ollama-models"

    def __init__(self, system: SystemAPI | None = None) -> None:
        self.system = system or SystemAPI()

    def collect(self) -> ProbeResult:
        try:
            models = tuple(
                ModelResourceState(id=model, provider="ollama", loaded=True, warm=None)
                for model in self.system.ollama_models()
            )
            return ProbeResult(probe_name=self.name, models=models)
        except Exception as exc:
            warning = _warning("ollama.models.unavailable", exc, "ollama")
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.unavailable,
                probe_warnings=(warning,),
                error_code=warning.code,
            )

    probe = collect


class OCRProbe:
    name = "ocr"

    def __init__(self, providers: Iterable[Any] | Any | None = None) -> None:
        if providers is None:
            providers = (UnlimitedOCRProvider(), PaddleOCRProvider())
        elif not isinstance(providers, Iterable) or isinstance(providers, (str, bytes)):
            providers = (providers,)
        self.providers = tuple(providers)

    def collect(self) -> ProbeResult:
        services: list[ServiceResourceState] = []
        models: list[ModelResourceState] = []
        warnings: list[ProbeWarning] = []
        for provider in self.providers:
            name_value = getattr(provider, "name", type(provider).__name__)
            provider_name = str(name_value() if callable(name_value) else name_value)
            service_id = (
                "unlimited-ocr" if provider_name == "unlimited" else provider_name
            )
            try:
                health = provider.health()
                info_method = getattr(provider, "info", None)
                info = info_method() if callable(info_method) else {}
                reachable = bool(
                    health.get(
                        "service_alive",
                        health.get("service_reachable", health.get("available", False)),
                    )
                )
                if provider_name != "unlimited" and "available" not in health:
                    reachable = str(health.get("status", "")).lower() in {
                        "ok",
                        "ready",
                        "healthy",
                    }
                services.append(
                    ServiceResourceState(
                        id=service_id,
                        state=str(health.get("status") or "unknown"),
                        reachable=reachable,
                    )
                )
                model_id = info.get("model_id") or health.get("model_id")
                if model_id:
                    models.append(
                        ModelResourceState(
                            id=str(model_id),
                            provider=service_id,
                            loaded=health.get("model_loaded", info.get("model_loaded")),
                            warm=health.get(
                                "inference_ready", info.get("inference_ready")
                            ),
                        )
                    )
            except Exception as exc:
                services.append(
                    ServiceResourceState(
                        id=service_id, state="unknown", reachable=False
                    )
                )
                warnings.append(_warning("ocr.probe.failed", exc, service_id))
        services.sort(key=lambda item: item.id)
        models.sort(key=lambda item: (item.provider or "", item.id))
        return ProbeResult(
            probe_name=self.name,
            status=_status(warnings, has_data=bool(services)),
            services=tuple(services),
            models=tuple(models),
            probe_warnings=tuple(warnings),
        )

    probe = collect


class ComfyUIProbe:
    name = "comfyui"

    def __init__(self, provider: ComfyUIProvider | None = None) -> None:
        self.provider = provider or ComfyUIProvider()

    def collect(self) -> ProbeResult:
        try:
            available = self.provider.available()
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.success if available else ProbeStatus.unavailable,
                services=(
                    ServiceResourceState(
                        id="comfyui",
                        state="available" if available else "unavailable",
                        reachable=available,
                    ),
                ),
            )
        except Exception as exc:
            warning = _warning("comfyui.probe.failed", exc, "comfyui")
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.failed,
                services=(
                    ServiceResourceState(
                        id="comfyui", state="unknown", reachable=False
                    ),
                ),
                probe_warnings=(warning,),
                error_code=warning.code,
            )

    probe = collect


class EmbeddingProbe:
    name = "models"

    def __init__(self, registry: EmbeddingRegistry | None = None) -> None:
        self.registry = registry or EmbeddingRegistry()

    def collect(self) -> ProbeResult:
        services: list[ServiceResourceState] = []
        models: list[ModelResourceState] = []
        warnings: list[ProbeWarning] = []
        for provider in self.registry.list():
            provider_id = str(provider.id)
            try:
                health = provider.health()
                services.append(
                    ServiceResourceState(
                        id=provider_id,
                        state=str(health.status),
                        reachable=bool(health.available),
                    )
                )
                models.append(
                    ModelResourceState(
                        id=str(getattr(health, "provider", provider_id)),
                        provider=provider_id,
                        loaded=health.model_loaded,
                        warm=bool(health.available and health.model_loaded),
                    )
                )
            except Exception as exc:
                services.append(
                    ServiceResourceState(
                        id=provider_id, state="unknown", reachable=False
                    )
                )
                warnings.append(_warning("embedding.probe.failed", exc, provider_id))
        services.sort(key=lambda item: item.id)
        models.sort(key=lambda item: (item.provider or "", item.id))
        return ProbeResult(
            probe_name=self.name,
            status=_status(warnings, has_data=bool(services)),
            services=tuple(services),
            models=tuple(models),
            probe_warnings=tuple(warnings),
        )

    probe = collect


ModelProbe = EmbeddingProbe


class RemoteProbe:
    """Compatibility observation of configured AEGIS remote runtimes."""

    name = "remote-runtime"

    def __init__(
        self,
        config: RemoteRuntimeConfig | None = None,
        client_factory: Callable[..., RemoteRuntimeClient] = RemoteRuntimeClient,
    ) -> None:
        self.config = config or load_remote_runtime_config()
        self.client_factory = client_factory

    def collect(self) -> ProbeResult:
        services: list[ServiceResourceState] = []
        warnings: list[ProbeWarning] = []
        for node_id, node in sorted(self.config.nodes.items()):
            resource = f"remote-runtime:{node_id}"
            if not self.config.enabled or not node.enabled:
                services.append(
                    ServiceResourceState(id=resource, state="disabled", reachable=False)
                )
                continue
            try:
                health = self.client_factory(
                    node,
                    connect_timeout=self.config.connect_timeout_seconds,
                    read_timeout=self.config.read_timeout_seconds,
                ).health()
                state = str(health.get("status") or "unknown")
                services.append(
                    ServiceResourceState(
                        id=resource,
                        state=state,
                        reachable=state in {"ok", "ready", "healthy"},
                    )
                )
            except Exception as exc:
                services.append(
                    ServiceResourceState(
                        id=resource, state="unreachable", reachable=False
                    )
                )
                warnings.append(_warning("remote.probe.failed", exc, resource))
        return ProbeResult(
            probe_name=self.name,
            status=_status(warnings, has_data=bool(services)),
            services=tuple(services),
            probe_warnings=tuple(warnings),
        )

    probe = collect


class GreenBoostRemoteProbe:
    """Read a remote snapshot exclusively through the RFC-055 client."""

    name = "greenboost-remote"

    def __init__(
        self,
        config: GreenBoostConfig | None = None,
        client_factory: Callable[..., GreenBoostClient] = GreenBoostClient,
    ) -> None:
        self.config = config or get_greenboost_config()
        self.client_factory = client_factory

    def collect(self) -> ProbeResult:
        if not self.config.enabled:
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.disabled,
                error_code="greenboost.disabled",
            )
        try:
            with self.client_factory(self.config) as client:
                snapshot = client.snapshot()
            return ProbeResult(probe_name=self.name, remote_snapshot=snapshot)
        except NodeUnavailable as exc:
            warning = _warning("greenboost.snapshot.unsupported", exc, "greenboost")
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.unsupported,
                probe_warnings=(warning,),
                error_code=warning.code,
            )
        except TimeoutError as exc:
            warning = _warning("greenboost.snapshot.timeout", exc, "greenboost")
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.unavailable,
                probe_warnings=(warning,),
                error_code=warning.code,
            )
        except AuthenticationError as exc:
            warning = _warning("greenboost.snapshot.authentication", exc, "greenboost")
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.failed,
                probe_warnings=(warning,),
                error_code=warning.code,
            )
        except (ProtocolError, GreenBoostError) as exc:
            warning = _warning("greenboost.snapshot.failed", exc, "greenboost")
            return ProbeResult(
                probe_name=self.name,
                status=ProbeStatus.failed,
                probe_warnings=(warning,),
                error_code=warning.code,
            )

    probe = collect


class ResourceProbe:
    """Deterministically merge one synchronous pass into one ResourceSnapshot."""

    name = "composite"

    def __init__(
        self,
        probes: Iterable[Any] | None = None,
        *,
        node: NodeReference | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.probes = tuple(probes) if probes is not None else self._configured_probes()
        self.node = node or NodeReference(
            id=socket.gethostname(), scope=NodeScope.local
        )
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _configured_probes() -> tuple[Any, ...]:
        config = get_greenboost_config()
        settings = config.probes
        if not settings.enabled:
            return ()
        probes: list[Any] = []
        if settings.local_system.enabled:
            probes.append(HostProbe())
        if settings.nvidia.enabled:
            probes.append(NvidiaGpuProbe())
        # With GBIP enabled the Ubuntu service owns Docker/Ollama/model discovery.
        # Disabled GBIP retains the legacy local workstation observation pass.
        if not config.enabled:
            if settings.services.enabled:
                probes.extend(
                    (DockerProbe(), OllamaProbe(), OCRProbe(), ComfyUIProbe())
                )
            if settings.models.enabled:
                probes.extend((OllamaModelProbe(), EmbeddingProbe()))
        if settings.remote.enabled:
            probes.extend((RemoteProbe(), GreenBoostRemoteProbe(config)))
        return tuple(probes)

    def results(self) -> tuple[ProbeResult, ...]:
        results: list[ProbeResult] = []
        for probe in self.probes:
            try:
                operation = getattr(probe, "collect", None) or probe.probe
                results.append(operation())
            except Exception as exc:
                name = str(getattr(probe, "name", type(probe).__name__))
                warning = _warning("resource.probe.failed", exc, name)
                results.append(
                    ProbeResult(
                        probe_name=name,
                        status=ProbeStatus.failed,
                        probe_warnings=(warning,),
                        error_code=warning.code,
                    )
                )
        return tuple(results)

    def collect(self) -> ResourceSnapshot:
        return self.collect_results(self.results())

    def collect_results(
        self,
        results: Iterable[ProbeResult],
        *,
        warn_separate_remote: bool = True,
    ) -> ResourceSnapshot:
        """Build the local snapshot from an already completed probe pass."""
        cpu, ram, disk = CPUState(), MemoryState(), DiskState()
        gpus: dict[str, GPUState] = {}
        services: dict[str, ServiceResourceState] = {}
        models: dict[tuple[str, str], ModelResourceState] = {}
        warnings: list[ProbeWarning] = []
        remote: ResourceSnapshot | None = None
        for result in results:
            if result.cpu is not None:
                cpu = result.cpu
            if result.ram is not None:
                ram = result.ram
            if result.disk is not None:
                disk = result.disk
            for gpu in result.gpus:
                gpus[gpu.id or gpu.name or str(len(gpus))] = gpu
            for service in result.services:
                services[service.id] = service
            for model in result.models:
                models[(model.provider or "", model.id)] = model
            warnings.extend(result.warnings)
            if result.remote_snapshot is not None:
                remote = result.remote_snapshot
        if remote is not None:
            if remote.node == self.node:
                if remote.timestamp > self.clock():
                    warnings.append(
                        _warning(
                            "resource.clock.skew",
                            "Remote snapshot timestamp is in the future",
                            remote.node.id,
                        )
                    )
                for gpu in remote.gpus:
                    gpus.setdefault(gpu.id or gpu.name or str(len(gpus)), gpu)
                for service in remote.services:
                    services.setdefault(service.id, service)
                for model in remote.models:
                    models.setdefault((model.provider or "", model.id), model)
                warnings.extend(remote.probe_warnings)
            elif warn_separate_remote:
                warnings.append(
                    _warning(
                        "resource.remote.separate-node",
                        "Remote snapshot belongs to a different node and cannot be embedded in the single-node ResourceSnapshot contract",
                        remote.node.id,
                    )
                )
        timestamp = self.clock()
        return ResourceSnapshot(
            timestamp=timestamp,
            node=self.node,
            cpu=cpu,
            ram=ram,
            gpus=tuple(
                sorted(gpus.values(), key=lambda item: (item.id or "", item.name or ""))
            ),
            disk=disk,
            services=tuple(sorted(services.values(), key=lambda item: item.id)),
            models=tuple(
                sorted(models.values(), key=lambda item: (item.provider or "", item.id))
            ),
            probe_warnings=tuple(warnings),
        )

    probe = collect


CompositeResourceProbe = ResourceProbe
