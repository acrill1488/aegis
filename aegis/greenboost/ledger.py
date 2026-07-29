"""Thread-safe, in-memory history and statistics for resource snapshots."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from statistics import fmean
from threading import RLock

from .contracts import ContractModel, ResourceSnapshot


DEFAULT_LEDGER_CAPACITY = 1_024


class ResourceStatistics(ContractModel):
    """Immutable node-level aggregate view over resource snapshots.

    VRAM field names are retained for API compatibility; their values represent
    per-snapshot totals across all GPUs with known measurements on the node.
    """

    snapshot_count: int
    average_cpu_load: float | None = None
    average_ram_usage_mb: float | None = None
    average_vram_usage_mb: float | None = None
    peak_cpu_load: float | None = None
    peak_ram_usage_mb: int | None = None
    peak_vram_usage_mb: int | None = None
    minimum_free_vram_mb: int | None = None
    oldest_timestamp: datetime | None = None
    latest_timestamp: datetime | None = None


class ResourceLedger:
    """Bounded snapshot history without polling, persistence, or policy."""

    def __init__(self, capacity: int = DEFAULT_LEDGER_CAPACITY) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self._snapshots: deque[ResourceSnapshot] = deque(maxlen=capacity)
        self._lock = RLock()

    @property
    def capacity(self) -> int:
        """Maximum number of retained snapshots."""

        return self._snapshots.maxlen or 0

    def append(self, snapshot: ResourceSnapshot) -> None:
        """Append an immutable snapshot, evicting the oldest at capacity."""

        if not isinstance(snapshot, ResourceSnapshot):
            raise TypeError("snapshot must be a ResourceSnapshot")
        with self._lock:
            self._snapshots.append(snapshot)

    def latest(self) -> ResourceSnapshot | None:
        """Return the most recently appended snapshot, if any."""

        with self._lock:
            return self._snapshots[-1] if self._snapshots else None

    def history(self) -> tuple[ResourceSnapshot, ...]:
        """Return an immutable, oldest-to-newest snapshot view."""

        with self._lock:
            return tuple(self._snapshots)

    def window(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[ResourceSnapshot, ...]:
        """Return snapshots whose UTC timestamps fall in the inclusive interval."""

        normalized_start = _utc_boundary(start, "start")
        normalized_end = _utc_boundary(end, "end")
        if normalized_start is not None and normalized_end is not None:
            if normalized_start > normalized_end:
                raise ValueError("start cannot be later than end")
        with self._lock:
            return tuple(
                snapshot
                for snapshot in self._snapshots
                if (normalized_start is None or snapshot.timestamp >= normalized_start)
                and (normalized_end is None or snapshot.timestamp <= normalized_end)
            )

    def statistics(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> ResourceStatistics:
        """Return read-only aggregates for the retained history or a time window."""

        snapshots = self.window(start, end)
        cpu_loads = [
            snapshot.cpu.utilization_percent
            for snapshot in snapshots
            if snapshot.cpu.utilization_percent is not None
        ]
        ram_usage = [
            snapshot.ram.used_mb
            for snapshot in snapshots
            if snapshot.ram.used_mb is not None
        ]
        vram_usage = _snapshot_vram_totals(snapshots, "used_mb")
        free_vram = _snapshot_vram_totals(snapshots, "available_mb")
        timestamps = [snapshot.timestamp for snapshot in snapshots]
        return ResourceStatistics(
            snapshot_count=len(snapshots),
            average_cpu_load=_average(cpu_loads),
            average_ram_usage_mb=_average(ram_usage),
            average_vram_usage_mb=_average(vram_usage),
            peak_cpu_load=max(cpu_loads, default=None),
            peak_ram_usage_mb=max(ram_usage, default=None),
            peak_vram_usage_mb=max(vram_usage, default=None),
            minimum_free_vram_mb=min(free_vram, default=None),
            oldest_timestamp=min(timestamps, default=None),
            latest_timestamp=max(timestamps, default=None),
        )


def _average(values: list[float | int]) -> float | None:
    return fmean(values) if values else None


def _snapshot_vram_totals(
    snapshots: tuple[ResourceSnapshot, ...],
    field: str,
) -> list[int]:
    totals: list[int] = []
    for snapshot in snapshots:
        known_values = [
            value
            for gpu in snapshot.gpus
            if (value := getattr(gpu.vram, field)) is not None
        ]
        if known_values:
            totals.append(sum(known_values))
    return totals


def _utc_boundary(value: datetime | None, name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)
