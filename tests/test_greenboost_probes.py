from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from aegis.greenboost.contracts import NodeReference, NodeScope, ResourceSnapshot
from aegis.greenboost.probes import (
    ComfyUIProbe, DockerProbe, EmbeddingProbe, GPUProbe, HostProbe, OCRProbe,
    OllamaProbe, ProbeResult, RemoteProbe, ResourceProbe,
)
from aegis.remote.config import RemoteNodeConfig, RemoteRuntimeConfig
from aegis.system.models import CPUInfo, DiskInfo, GPUInfo, MemoryInfo, ServiceInfo


class FakeSystem:
    def cpu(self):
        return CPUInfo(percent=25, cores=4, logical_cores=8)

    def memory(self):
        return MemoryInfo(total_gb=16, used_gb=6, free_gb=10, percent=37.5)

    def storage(self):
        return [DiskInfo(path="x", total_gb=100, used_gb=40, free_gb=60, percent=40)]

    def gpu(self):
        return [GPUInfo("RTX", 20, 8192, 2048, 6144, 55)]

    def docker(self):
        return ServiceInfo("docker", True, "Docker 1")

    def ollama(self):
        return ServiceInfo("ollama", False, "offline")


def test_host_and_gpu_probes_map_existing_system_api():
    host = HostProbe(FakeSystem()).probe()
    gpu = GPUProbe(FakeSystem()).probe()
    assert host.cpu.logical_cores == 8
    assert host.cpu.available_cores == 6
    assert host.ram.available_mb == 10240
    assert host.disk.used_mb == 40960
    assert gpu.gpus[0].vram.available_mb == 6144


def test_system_service_probes_map_status_without_new_checks():
    docker = DockerProbe(FakeSystem()).probe().services[0]
    ollama = OllamaProbe(FakeSystem()).probe().services[0]
    assert (docker.state, docker.reachable) == ("available", True)
    assert (ollama.state, ollama.reachable) == ("unavailable", False)


def test_ocr_probe_reuses_health_and_info():
    provider = SimpleNamespace(
        health=lambda: {"status": "ready", "service_alive": True, "model_loaded": True},
        info=lambda: {"model_id": "ocr/model", "inference_ready": True},
    )
    provider.name = "unlimited"
    result = OCRProbe(provider).probe()
    assert result.services[0].reachable is True
    assert result.models[0].id == "ocr/model"
    assert result.models[0].loaded is True
    assert result.models[0].warm is True


def test_comfyui_probe_reuses_provider_availability():
    result = ComfyUIProbe(SimpleNamespace(available=lambda: True)).probe()
    assert result.services[0].id == "comfyui"
    assert result.services[0].reachable is True


def test_embedding_probe_maps_health_and_isolates_provider_failure():
    healthy = SimpleNamespace(id="bge", health=lambda: SimpleNamespace(
        status="healthy", available=True, provider="bge-m3", model_loaded=True,
    ))
    broken = SimpleNamespace(id="broken", health=lambda: (_ for _ in ()).throw(RuntimeError("bad")))
    registry = SimpleNamespace(list=lambda: [healthy, broken])
    result = EmbeddingProbe(registry).probe()
    assert [service.id for service in result.services] == ["bge", "broken"]
    assert result.models[0].warm is True
    assert result.warnings[0].resource == "broken"


def _remote_config(enabled=True):
    return RemoteRuntimeConfig(
        enabled=enabled, default_node="node", nodes={
            "node": RemoteNodeConfig(id="node", base_url="http://node", enabled=True),
        }, connect_timeout_seconds=1, read_timeout_seconds=2, server={},
    )


def test_remote_probe_reuses_versioned_health_client():
    calls = []
    class Client:
        def __init__(self, node, **kwargs):
            calls.append((node.id, kwargs))
        def health(self):
            return {"status": "healthy"}
    result = RemoteProbe(_remote_config(), Client).probe()
    assert result.services[0].reachable is True
    assert calls == [("node", {"connect_timeout": 1, "read_timeout": 2})]


def test_remote_probe_does_not_contact_disabled_runtime():
    result = RemoteProbe(_remote_config(False), lambda *args, **kwargs: pytest.fail("called")).probe()
    assert result.services[0].state == "disabled"


def test_resource_probe_merges_fragments_into_frozen_snapshot():
    now = datetime(2026, 7, 26, tzinfo=timezone.utc)
    fragments = [
        SimpleNamespace(probe=lambda: HostProbe(FakeSystem()).probe()),
        SimpleNamespace(probe=lambda: GPUProbe(FakeSystem()).probe()),
        SimpleNamespace(probe=lambda: DockerProbe(FakeSystem()).probe()),
    ]
    snapshot = ResourceProbe(
        fragments, node=NodeReference(id="local", scope=NodeScope.local), clock=lambda: now,
    ).probe()
    assert isinstance(snapshot, ResourceSnapshot)
    assert snapshot.timestamp == now
    assert snapshot.gpus[0].name == "RTX"
    assert snapshot.services[0].id == "docker"
    with pytest.raises(Exception):
        snapshot.cpu = snapshot.cpu


def test_resource_probe_turns_unexpected_child_failure_into_warning():
    broken = SimpleNamespace(probe=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    snapshot = ResourceProbe([broken], clock=lambda: datetime.now(timezone.utc)).probe()
    assert snapshot.probe_warnings[0].code == "resource.probe.failed"


def test_probe_result_rejects_mutation_and_serializes_with_snapshot_name():
    result = ProbeResult()
    with pytest.raises(Exception):
        result.gpus = ()
    assert "probe_warnings" in result.model_dump(by_alias=True)
