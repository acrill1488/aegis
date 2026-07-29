from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aegis.greenboost import ResourceLedger, ResourceStatistics
from aegis.greenboost.contracts import (
    CPUState,
    GPUState,
    MemoryState,
    NodeReference,
    NodeScope,
    ResourceSnapshot,
)


BASE = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
NODE = NodeReference(id="local", scope=NodeScope.local)


def snapshot(
    offset: int,
    *,
    cpu: float | None = None,
    ram: int | None = None,
    vram: int | None = None,
    free_vram: int | None = None,
) -> ResourceSnapshot:
    gpus = ()
    if vram is not None or free_vram is not None:
        gpus = (GPUState(vram=MemoryState(used_mb=vram, available_mb=free_vram)),)
    return ResourceSnapshot(
        timestamp=BASE + timedelta(seconds=offset),
        node=NODE,
        cpu=CPUState(utilization_percent=cpu),
        ram=MemoryState(used_mb=ram),
        gpus=gpus,
    )


def multi_gpu_snapshot(
    offset: int,
    *vram: tuple[int | None, int | None],
) -> ResourceSnapshot:
    return ResourceSnapshot(
        timestamp=BASE + timedelta(seconds=offset),
        node=NODE,
        gpus=tuple(
            GPUState(vram=MemoryState(used_mb=used, available_mb=available))
            for used, available in vram
        ),
    )


def test_empty_ledger_views_and_statistics():
    ledger = ResourceLedger()
    assert ledger.latest() is None
    assert ledger.history() == ()
    assert ledger.window() == ()
    assert ledger.statistics() == ResourceStatistics(snapshot_count=0)


def test_append_preserves_insertion_order_and_snapshot_identity():
    ledger = ResourceLedger()
    later = snapshot(2)
    earlier = snapshot(1)
    ledger.append(later)
    ledger.append(earlier)
    assert ledger.history() == (later, earlier)
    assert ledger.latest() is earlier


def test_history_and_statistics_are_immutable_and_snapshot_is_not_mutated():
    ledger = ResourceLedger()
    value = snapshot(0, cpu=25)
    ledger.append(value)
    history = ledger.history()
    assert isinstance(history, tuple)
    with pytest.raises(ValidationError):
        value.cpu = CPUState(utilization_percent=50)
    with pytest.raises(ValidationError):
        ledger.statistics().snapshot_count = 2
    assert ledger.latest() is value


def test_window_filters_inclusively_and_validates_boundaries():
    ledger = ResourceLedger()
    for offset in range(5):
        ledger.append(snapshot(offset))
    assert ledger.window(BASE + timedelta(seconds=1), BASE + timedelta(seconds=3)) == tuple(
        snapshot(offset) for offset in range(1, 4)
    )
    assert ledger.window(start=BASE + timedelta(seconds=3)) == tuple(
        snapshot(offset) for offset in range(3, 5)
    )
    assert ledger.window(end=BASE + timedelta(seconds=1)) == tuple(
        snapshot(offset) for offset in range(2)
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        ledger.window(start=BASE.replace(tzinfo=None))
    with pytest.raises(ValueError, match="later"):
        ledger.window(BASE + timedelta(seconds=2), BASE)


def test_bounded_capacity_evicts_oldest_snapshot():
    ledger = ResourceLedger(capacity=3)
    for offset in range(5):
        ledger.append(snapshot(offset))
    assert ledger.capacity == 3
    assert ledger.history() == tuple(snapshot(offset) for offset in range(2, 5))


@pytest.mark.parametrize("capacity", [0, -1, 1.5, True])
def test_capacity_must_be_a_positive_integer(capacity):
    with pytest.raises(ValueError, match="positive integer"):
        ResourceLedger(capacity=capacity)


def test_statistics_are_correct_and_ignore_unknown_measurements():
    ledger = ResourceLedger()
    ledger.append(snapshot(0, cpu=10, ram=100, vram=200, free_vram=800))
    ledger.append(snapshot(1))
    ledger.append(snapshot(2, cpu=30, ram=300, vram=600, free_vram=400))
    assert ledger.statistics() == ResourceStatistics(
        snapshot_count=3,
        average_cpu_load=20,
        average_ram_usage_mb=200,
        average_vram_usage_mb=400,
        peak_cpu_load=30,
        peak_ram_usage_mb=300,
        peak_vram_usage_mb=600,
        minimum_free_vram_mb=400,
        oldest_timestamp=BASE,
        latest_timestamp=BASE + timedelta(seconds=2),
    )


def test_vram_statistics_sum_devices_once_per_snapshot():
    ledger = ResourceLedger()
    ledger.append(multi_gpu_snapshot(0, (100, 900), (300, 700)))
    ledger.append(multi_gpu_snapshot(1, (800, 200)))
    stats = ledger.statistics()
    assert stats.average_vram_usage_mb == 600
    assert stats.peak_vram_usage_mb == 800
    assert stats.minimum_free_vram_mb == 200
    assert stats.average_vram_usage_mb != 400


def test_vram_statistics_sum_known_devices_and_ignore_unknown_devices():
    ledger = ResourceLedger()
    ledger.append(multi_gpu_snapshot(0, (100, None), (None, 700), (300, 200)))
    stats = ledger.statistics()
    assert stats.average_vram_usage_mb == 400
    assert stats.peak_vram_usage_mb == 400
    assert stats.minimum_free_vram_mb == 900


def test_unknown_and_absent_gpu_measurements_remain_unknown():
    no_gpus = ResourceLedger()
    no_gpus.append(snapshot(0))
    assert no_gpus.statistics().average_vram_usage_mb is None
    assert no_gpus.statistics().peak_vram_usage_mb is None
    assert no_gpus.statistics().minimum_free_vram_mb is None

    unknown = ResourceLedger()
    unknown.append(multi_gpu_snapshot(0, (None, None), (None, None)))
    assert unknown.statistics().average_vram_usage_mb is None
    assert unknown.statistics().peak_vram_usage_mb is None
    assert unknown.statistics().minimum_free_vram_mb is None


def test_windowed_vram_statistics_use_node_level_totals():
    ledger = ResourceLedger()
    ledger.append(multi_gpu_snapshot(0, (100, 500), (300, 300)))
    ledger.append(multi_gpu_snapshot(1, (800, 200)))
    stats = ledger.statistics(start=BASE + timedelta(seconds=1))
    assert stats.snapshot_count == 1
    assert stats.average_vram_usage_mb == 800
    assert stats.peak_vram_usage_mb == 800
    assert stats.minimum_free_vram_mb == 200


def test_single_gpu_vram_statistics_remain_unchanged():
    ledger = ResourceLedger()
    ledger.append(snapshot(0, vram=250, free_vram=750))
    stats = ledger.statistics()
    assert stats.average_vram_usage_mb == 250
    assert stats.peak_vram_usage_mb == 250
    assert stats.minimum_free_vram_mb == 750


def test_single_snapshot_and_windowed_statistics():
    ledger = ResourceLedger()
    ledger.append(snapshot(0, cpu=10))
    ledger.append(snapshot(1, cpu=20))
    stats = ledger.statistics(BASE + timedelta(seconds=1))
    assert stats.snapshot_count == 1
    assert stats.average_cpu_load == 20
    assert stats.oldest_timestamp == stats.latest_timestamp == BASE + timedelta(seconds=1)


def test_large_history_remains_bounded_and_ordered():
    ledger = ResourceLedger(capacity=1_000)
    for offset in range(10_000):
        ledger.append(snapshot(offset))
    history = ledger.history()
    assert len(history) == 1_000
    assert history[0].timestamp == BASE + timedelta(seconds=9_000)
    assert history[-1].timestamp == BASE + timedelta(seconds=9_999)


def test_append_rejects_non_snapshot_values():
    ledger = ResourceLedger()
    with pytest.raises(TypeError, match="ResourceSnapshot"):
        ledger.append(object())
