from datetime import datetime, timezone
from types import SimpleNamespace

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.config.services import GreenBoostConfig
from aegis.greenboost.contracts import NodeReference, NodeScope, ResourceSnapshot
from aegis.greenboost.probes import (
    DockerProbe,
    GreenBoostRemoteProbe,
    NvidiaGpuProbe,
    ProbeStatus,
    ResourceProbe,
)


NOW = datetime(2026, 7, 29, tzinfo=timezone.utc)


class FakeNVML:
    NVML_TEMPERATURE_GPU = 0

    def __init__(self):
        self.shutdown = False

    def nvmlInit(self):
        pass

    def nvmlShutdown(self):
        self.shutdown = True

    def nvmlDeviceGetCount(self):
        return 2

    def nvmlDeviceGetHandleByIndex(self, index):
        if index == 1:
            raise RuntimeError("device failed")
        return index

    def nvmlDeviceGetMemoryInfo(self, handle):
        return SimpleNamespace(total=8 * 1024**3, used=2 * 1024**3, free=6 * 1024**3)

    def nvmlDeviceGetUtilizationRates(self, handle):
        return SimpleNamespace(gpu=25)

    def nvmlDeviceGetTemperature(self, handle, sensor):
        return 55

    def nvmlDeviceGetUUID(self, handle):
        return "GPU-1"

    def nvmlDeviceGetName(self, handle):
        return "RTX"


def test_nvidia_probe_isolates_device_failure_and_shuts_down():
    nvml = FakeNVML()
    result = NvidiaGpuProbe(nvml).collect()
    assert result.status is ProbeStatus.partial
    assert result.gpus[0].id == "GPU-1"
    assert nvml.shutdown is True


def test_greenboost_remote_probe_is_disabled_without_client_call():
    config = GreenBoostConfig(enabled=False)
    result = GreenBoostRemoteProbe(
        config, lambda *_: (_ for _ in ()).throw(AssertionError())
    ).collect()
    assert result.status is ProbeStatus.disabled


def test_enabled_gbip_keeps_docker_and_models_off_windows(monkeypatch):
    monkeypatch.setattr(
        "aegis.greenboost.probes.get_greenboost_config",
        lambda: GreenBoostConfig(enabled=True),
    )
    probes = ResourceProbe._configured_probes()
    assert not any(isinstance(probe, DockerProbe) for probe in probes)
    assert {probe.name for probe in probes} == {
        "local-system",
        "nvidia",
        "remote-runtime",
        "greenboost-remote",
    }


def test_remote_node_is_not_folded_into_local_single_node_contract():
    remote = ResourceSnapshot(
        timestamp=NOW, node=NodeReference(id="remote", scope=NodeScope.remote)
    )
    fragment = SimpleNamespace(
        collect=lambda: SimpleNamespace(
            cpu=None,
            ram=None,
            disk=None,
            gpus=(),
            services=(),
            models=(),
            warnings=(),
            remote_snapshot=remote,
        )
    )
    snapshot = ResourceProbe(
        (fragment,),
        node=NodeReference(id="local", scope=NodeScope.local),
        clock=lambda: NOW,
    ).collect()
    assert snapshot.node.id == "local"
    assert snapshot.probe_warnings[0].code == "resource.remote.separate-node"


def test_probes_json_is_machine_clean(monkeypatch):
    monkeypatch.setattr(
        "aegis.greenboost.cli.ResourceProbe",
        lambda: ResourceProbe((), clock=lambda: NOW),
    )
    result = CliRunner().invoke(app, ["greenboost", "probes", "--json"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "[]"
