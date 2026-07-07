from dataclasses import dataclass


@dataclass
class CPUInfo:
    percent: float
    cores: int
    logical_cores: int


@dataclass
class MemoryInfo:
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float


@dataclass
class DiskInfo:
    path: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float


@dataclass
class GPUInfo:
    name: str
    load_percent: float | None
    memory_total_mb: float | None
    memory_used_mb: float | None
    memory_free_mb: float | None
    temperature_c: float | None


@dataclass
class NetworkInfo:
    connected: bool
    hostname: str
    ip_addresses: list[str]


@dataclass
class ServiceInfo:
    name: str
    available: bool
    details: str = ""


@dataclass
class SystemStatus:
    cpu: CPUInfo
    memory: MemoryInfo
    disks: list[DiskInfo]
    gpus: list[GPUInfo]
    network: NetworkInfo
    services: list[ServiceInfo]
