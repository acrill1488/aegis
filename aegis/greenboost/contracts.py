"""Validated, side-effect-free resource contracts for GreenBoost."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from math import isfinite
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)


MAX_METADATA_BYTES = 16_384
MAX_METADATA_DEPTH = 6
MAX_METADATA_ITEMS = 128
MAX_METADATA_KEY_LENGTH = 128
MAX_METADATA_STRING_LENGTH = 4_096
MIN_METADATA_INTEGER = -(2**63)
MAX_METADATA_INTEGER = 2**63 - 1

_RESERVED_METADATA_KEYS = frozenset(
    {
        "critical_authorized",
        "execution_priority",
        "priority",
        "priority_authorized",
        "priority_trusted",
        "requires_priority_authorization",
    }
)


class _FrozenDict(Mapping[str, Any]):
    """Small immutable mapping used only for validated JSON metadata."""

    __slots__ = ("_items", "_lookup")

    def __init__(self, items: Sequence[tuple[str, Any]] = ()) -> None:
        self._items = tuple(sorted(items, key=lambda item: item[0]))
        self._lookup = dict(self._items)

    def __getitem__(self, key: str) -> Any:
        return self._lookup[key]

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._items)

    def __repr__(self) -> str:
        return repr(dict(self._items))


class _FrozenList(Sequence[Any]):
    """Small immutable sequence used only for validated JSON metadata."""

    __slots__ = ("_items",)

    def __init__(self, items: Sequence[Any] = ()) -> None:
        self._items = tuple(items)

    def __getitem__(self, index: int | slice) -> Any:
        return self._items[index]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Sequence) and not isinstance(other, (str, bytes, bytearray)):
            return tuple(self) == tuple(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._items)

    def __repr__(self) -> str:
        return repr(list(self._items))


ImmutableMetadata = Annotated[
    Any,
    BeforeValidator(lambda value: _validate_and_freeze_metadata(value)),
    PlainSerializer(lambda value: _metadata_to_plain(value), return_type=dict[str, Any]),
]


class ResourcePressure(StrEnum):
    """Observed pressure level for a node resource snapshot."""

    unknown = "unknown"
    normal = "normal"
    elevated = "elevated"
    high = "high"
    critical = "critical"


class ReservationState(StrEnum):
    """Data state of a resource reservation."""

    pending = "pending"
    active = "active"
    suspected_stale = "suspected_stale"
    releasing = "releasing"
    released = "released"
    failed = "failed"


class ExecutionPriority(StrEnum):
    """Requested GreenBoost scheduling priority, subject to authorization."""

    critical = "critical"
    interactive = "interactive"
    normal = "normal"
    background = "background"
    maintenance = "maintenance"


class NodeScope(StrEnum):
    """Whether a resource node is local to or remote from the caller."""

    local = "local"
    remote = "remote"


class GreenBoostMode(StrEnum):
    """GreenBoost operating mode."""

    disabled = "disabled"
    observe = "observe"
    enforce = "enforce"


class ResourceProfile(StrEnum):
    """Named resource-policy profile."""

    performance = "performance"
    balanced = "balanced"
    eco = "eco"
    emergency = "emergency"


class ContractModel(BaseModel):
    """Common immutable configuration for GreenBoost wire contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class NodeReference(ContractModel):
    """Stable node identifier with an explicit local or remote scope."""

    id: str = Field(min_length=1, max_length=128)
    scope: NodeScope


class ResourceQuantities(ContractModel):
    """Concrete quantities committed by a reservation."""

    cpu_cores: float | None = Field(default=None, ge=0)
    ram_mb: int | None = Field(default=None, ge=0)
    vram_mb: int | None = Field(default=None, ge=0)
    disk_mb: int | None = Field(default=None, ge=0)
    gpu_exclusive: bool = False


class ResourceRequest(ContractModel):
    """Provider-neutral resource requirements without admission decisions."""

    execution_id: str = Field(min_length=1, max_length=256)
    capability: str = Field(min_length=1, max_length=256)
    provider: str | None = Field(default=None, min_length=1, max_length=256)
    service: str | None = Field(default=None, min_length=1, max_length=256)
    model: str | None = Field(default=None, min_length=1, max_length=512)
    node: NodeReference
    priority: ExecutionPriority = ExecutionPriority.normal
    cpu_cores_min: float | None = Field(default=None, ge=0)
    cpu_cores_preferred: float | None = Field(default=None, ge=0)
    ram_mb_min: int | None = Field(default=None, ge=0)
    ram_mb_preferred: int | None = Field(default=None, ge=0)
    vram_mb_min: int | None = Field(default=None, ge=0)
    vram_mb_preferred: int | None = Field(default=None, ge=0)
    disk_mb: int | None = Field(default=None, ge=0)
    gpu_required: bool = False
    gpu_exclusive: bool = False
    cpu_fallback_allowed: bool = False
    remote_allowed: bool = False
    preemptible: bool = False
    estimated_duration: timedelta | None = None
    queue_timeout: timedelta | None = None
    execution_timeout: timedelta | None = None
    metadata: ImmutableMetadata = Field(default_factory=_FrozenDict)

    @field_validator("estimated_duration", "queue_timeout", "execution_timeout")
    @classmethod
    def validate_positive_duration(cls, value: timedelta | None) -> timedelta | None:
        if value is not None and value <= timedelta(0):
            raise ValueError("durations and timeouts must be positive")
        return value

    @model_validator(mode="after")
    def validate_preferred_resources(self) -> Self:
        for minimum_name, preferred_name in (
            ("cpu_cores_min", "cpu_cores_preferred"),
            ("ram_mb_min", "ram_mb_preferred"),
            ("vram_mb_min", "vram_mb_preferred"),
        ):
            minimum = getattr(self, minimum_name)
            preferred = getattr(self, preferred_name)
            if minimum is not None and preferred is not None and preferred < minimum:
                raise ValueError(f"{preferred_name} cannot be lower than {minimum_name}")
        return self

    @property
    def requires_priority_authorization(self) -> bool:
        """Whether the orchestrator must authorize this requested priority."""
        return self.priority is ExecutionPriority.critical


class ResourceReservation(ContractModel):
    """Immutable reservation state record.

    Heartbeat renewal, suspected-stale transition, release, and failure are
    represented by constructing a newly validated ``ResourceReservation``.
    Reconciliation belongs to the future ResourceLedger and runtime.
    """

    reservation_id: str = Field(min_length=1, max_length=256)
    execution_id: str = Field(min_length=1, max_length=256)
    node: NodeReference
    resources: ResourceQuantities
    state: ReservationState = ReservationState.pending
    created_at: datetime
    lease_expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    lease_owner: str | None = Field(default=None, min_length=1, max_length=256)
    released_at: datetime | None = None
    owner: str = Field(min_length=1, max_length=256)
    reason: str | None = Field(default=None, max_length=2048)

    @field_validator("created_at", "lease_expires_at", "last_heartbeat_at", "released_at")
    @classmethod
    def validate_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reservation datetimes must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_timeline_and_state(self) -> Self:
        for name in ("lease_expires_at", "last_heartbeat_at", "released_at"):
            value = getattr(self, name)
            if value is not None and value < self.created_at:
                raise ValueError(f"{name} cannot precede created_at")
        if self.state is ReservationState.released and self.released_at is None:
            raise ValueError("released reservations require released_at")
        if self.state is not ReservationState.released and self.released_at is not None:
            raise ValueError("released_at is only valid for released reservations")
        if self.last_heartbeat_at is not None and self.lease_owner is None:
            raise ValueError("last_heartbeat_at requires lease_owner")
        return self


class CPUState(ContractModel):
    """Optional CPU telemetry; unavailable measurements remain unknown."""

    logical_cores: int | None = Field(default=None, ge=0)
    available_cores: float | None = Field(default=None, ge=0)
    utilization_percent: float | None = Field(default=None, ge=0, le=100)


class MemoryState(ContractModel):
    """Optional RAM or VRAM telemetry in megabytes."""

    total_mb: int | None = Field(default=None, ge=0)
    used_mb: int | None = Field(default=None, ge=0)
    reserved_mb: int | None = Field(default=None, ge=0)
    available_mb: int | None = Field(default=None, ge=0)


class GPUState(ContractModel):
    """Optional GPU identity, utilization, and VRAM state."""

    id: str | None = Field(default=None, max_length=256)
    name: str | None = Field(default=None, max_length=512)
    utilization_percent: float | None = Field(default=None, ge=0, le=100)
    temperature_celsius: float | None = None
    vram: MemoryState = Field(default_factory=MemoryState)


class DiskState(ContractModel):
    """Optional disk-capacity telemetry in megabytes."""

    total_mb: int | None = Field(default=None, ge=0)
    used_mb: int | None = Field(default=None, ge=0)
    available_mb: int | None = Field(default=None, ge=0)


class ServiceResourceState(ContractModel):
    """Observed service state without imposing a lifecycle state machine."""

    id: str = Field(min_length=1, max_length=256)
    state: str = Field(min_length=1, max_length=128)
    reachable: bool | None = None


class ModelResourceState(ContractModel):
    """Observed model load and warm state."""

    id: str = Field(min_length=1, max_length=512)
    provider: str | None = Field(default=None, min_length=1, max_length=256)
    loaded: bool | None = None
    warm: bool | None = None


class ProbeWarning(ContractModel):
    """Structured warning emitted by a future resource probe."""

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=2048)
    resource: str | None = Field(default=None, max_length=128)


class ResourceSnapshot(ContractModel):
    """Timestamped local or remote resource observation with explicit freshness."""

    timestamp: datetime
    node: NodeReference
    cpu: CPUState = Field(default_factory=CPUState)
    ram: MemoryState = Field(default_factory=MemoryState)
    gpus: tuple[GPUState, ...] = ()
    disk: DiskState = Field(default_factory=DiskState)
    services: tuple[ServiceResourceState, ...] = ()
    models: tuple[ModelResourceState, ...] = ()
    reservations: tuple[ResourceReservation, ...] = ()
    queue_depth: int | None = Field(default=None, ge=0)
    pressure: ResourcePressure = ResourcePressure.unknown
    probe_warnings: tuple[ProbeWarning, ...] = ()
    fresh_until: datetime | None = None

    @field_validator("timestamp", "fresh_until")
    @classmethod
    def validate_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("snapshot datetimes must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_freshness(self) -> Self:
        if self.fresh_until is not None and self.fresh_until < self.timestamp:
            raise ValueError("fresh_until cannot precede timestamp")
        return self


def _validate_and_freeze_metadata(value: Any) -> _FrozenDict:
    """Validate JSON metadata and return a deeply immutable representation."""

    if not isinstance(value, Mapping):
        raise ValueError("metadata must be a dictionary")

    item_count = 0
    active_container_ids: set[int] = set()

    def walk(item: Any, depth: int) -> Any:
        nonlocal item_count
        if depth > MAX_METADATA_DEPTH:
            raise ValueError(f"metadata exceeds maximum depth {MAX_METADATA_DEPTH}")
        if item is None or isinstance(item, bool):
            return item
        if isinstance(item, str):
            if len(item) > MAX_METADATA_STRING_LENGTH:
                raise ValueError(
                    f"metadata string exceeds maximum length {MAX_METADATA_STRING_LENGTH}"
                )
            return item
        if isinstance(item, int):
            if not MIN_METADATA_INTEGER <= item <= MAX_METADATA_INTEGER:
                raise ValueError("metadata integers must fit in a signed 64-bit value")
            return item
        if isinstance(item, float):
            if not isfinite(item):
                raise ValueError("metadata floats must be finite")
            return item
        if isinstance(item, (Mapping, list)):
            container_id = id(item)
            if container_id in active_container_ids:
                raise ValueError("metadata contains a circular dictionary or list reference")
            active_container_ids.add(container_id)
            try:
                item_count += len(item)
                if item_count > MAX_METADATA_ITEMS:
                    raise ValueError(
                        f"metadata exceeds maximum item count {MAX_METADATA_ITEMS}"
                    )
                if isinstance(item, Mapping):
                    frozen_items: list[tuple[str, Any]] = []
                    for key, nested in item.items():
                        if not isinstance(key, str):
                            raise ValueError("metadata object keys must be strings")
                        if len(key) > MAX_METADATA_KEY_LENGTH:
                            raise ValueError(
                                f"metadata key exceeds maximum length {MAX_METADATA_KEY_LENGTH}"
                            )
                        if key.casefold() in _RESERVED_METADATA_KEYS:
                            raise ValueError(
                                f"metadata key {key!r} is reserved for execution priority control"
                            )
                        frozen_items.append((key, walk(nested, depth + 1)))
                    return _FrozenDict(frozen_items)
                return _FrozenList([walk(nested, depth + 1) for nested in item])
            finally:
                active_container_ids.remove(container_id)
        raise ValueError(f"metadata value of type {type(item).__name__} is not JSON-compatible")

    frozen = walk(value, 0)
    if not isinstance(frozen, _FrozenDict):
        raise ValueError("metadata must be a dictionary")
    encoded = json.dumps(
        _metadata_to_plain(frozen), ensure_ascii=False, allow_nan=False, sort_keys=True
    ).encode("utf-8")
    if len(encoded) > MAX_METADATA_BYTES:
        raise ValueError(f"metadata exceeds maximum encoded size {MAX_METADATA_BYTES} bytes")
    return frozen


def _metadata_to_plain(value: Any) -> Any:
    """Convert immutable metadata containers back to ordinary JSON values."""

    if isinstance(value, _FrozenDict):
        return {key: _metadata_to_plain(item) for key, item in value.items()}
    if isinstance(value, _FrozenList):
        return [_metadata_to_plain(item) for item in value]
    return value
