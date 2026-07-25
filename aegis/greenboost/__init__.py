"""GreenBoost resource contracts and the legacy OCR resource adapter."""

from .contracts import (
    CPUState,
    DiskState,
    ExecutionPriority,
    GPUState,
    GreenBoostMode,
    MemoryState,
    ModelResourceState,
    NodeReference,
    NodeScope,
    ProbeWarning,
    ReservationState,
    ResourcePressure,
    ResourceProfile,
    ResourceQuantities,
    ResourceRequest,
    ResourceReservation,
    ResourceSnapshot,
    ServiceResourceState,
)

from .runtime import GreenBoostRuntime, GreenBoostSession

__all__ = [
    "CPUState",
    "DiskState",
    "ExecutionPriority",
    "GPUState",
    "GreenBoostMode",
    "GreenBoostRuntime",
    "GreenBoostSession",
    "MemoryState",
    "ModelResourceState",
    "NodeReference",
    "NodeScope",
    "ProbeWarning",
    "ReservationState",
    "ResourcePressure",
    "ResourceProfile",
    "ResourceQuantities",
    "ResourceRequest",
    "ResourceReservation",
    "ResourceSnapshot",
    "ServiceResourceState",
]
