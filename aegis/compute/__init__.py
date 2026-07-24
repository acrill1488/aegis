"""Minimal compute utilities for GPU-backed service handoff."""

from .gpu_service_handoff import (
    DEFAULT_GPU_SERVICES_CONFIG_PATH,
    GPUServiceHandoff,
    GPUServiceHandoffReport,
    select_service_for_task_type,
)

__all__ = [
    "DEFAULT_GPU_SERVICES_CONFIG_PATH",
    "GPUServiceHandoff",
    "GPUServiceHandoffReport",
    "select_service_for_task_type",
]
