import socket
import subprocess

import httpx
from aegis.config.services import get_service_base_url

from aegis.system.models import (
    CPUInfo,
    DiskInfo,
    GPUInfo,
    MemoryInfo,
    NetworkInfo,
    ServiceInfo,
    SystemStatus,
)

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only in incomplete environments.
    psutil = None


BYTES_PER_GB = 1024**3
class SystemAPI:
    """Public API for local system resource and service status."""

    def cpu(self) -> CPUInfo:
        self._require_psutil()
        return CPUInfo(
            percent=float(psutil.cpu_percent(interval=0.1)),
            cores=int(psutil.cpu_count(logical=False) or 0),
            logical_cores=int(psutil.cpu_count(logical=True) or 0),
        )

    def memory(self) -> MemoryInfo:
        self._require_psutil()
        memory = psutil.virtual_memory()
        return MemoryInfo(
            total_gb=self._gb(memory.total),
            used_gb=self._gb(memory.used),
            free_gb=self._gb(memory.available),
            percent=float(memory.percent),
        )

    def storage(self, paths: list[str] | None = None) -> list[DiskInfo]:
        self._require_psutil()
        target_paths = paths if paths is not None else self._disk_paths()
        disks: list[DiskInfo] = []

        for path in target_paths:
            try:
                usage = psutil.disk_usage(path)
            except (FileNotFoundError, OSError, PermissionError):
                continue
            disks.append(
                DiskInfo(
                    path=path,
                    total_gb=self._gb(usage.total),
                    used_gb=self._gb(usage.used),
                    free_gb=self._gb(usage.free),
                    percent=float(usage.percent),
                )
            )

        return disks

    def gpu(self) -> list[GPUInfo]:
        command = [
            "nvidia-smi",
            "--query-gpu=name,utilization.gpu,memory.total,memory.used,memory.free,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return []

        if result.returncode != 0:
            return []

        gpus: list[GPUInfo] = []
        for line in result.stdout.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 6:
                continue
            gpus.append(
                GPUInfo(
                    name=parts[0],
                    load_percent=self._float_or_none(parts[1]),
                    memory_total_mb=self._float_or_none(parts[2]),
                    memory_used_mb=self._float_or_none(parts[3]),
                    memory_free_mb=self._float_or_none(parts[4]),
                    temperature_c=self._float_or_none(parts[5]),
                )
            )
        return gpus

    def network(self) -> NetworkInfo:
        self._require_psutil()
        hostname = socket.gethostname()
        ip_addresses = self._ip_addresses()
        return NetworkInfo(
            connected=bool(ip_addresses),
            hostname=hostname,
            ip_addresses=ip_addresses,
        )

    def docker(self) -> ServiceInfo:
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            return ServiceInfo(name="docker", available=False, details=str(exc))

        details = result.stdout.strip() or result.stderr.strip()
        return ServiceInfo(
            name="docker",
            available=result.returncode == 0,
            details=details,
        )

    def ollama(self) -> ServiceInfo:
        try:
            response = httpx.get(
                f"{get_service_base_url('ollama')}/api/tags", timeout=5, trust_env=False
            )
        except Exception as exc:
            return ServiceInfo(name="ollama", available=False, details=str(exc))

        if response.status_code != 200:
            return ServiceInfo(
                name="ollama",
                available=False,
                details=f"HTTP {response.status_code}",
            )

        try:
            data = response.json()
        except ValueError:
            return ServiceInfo(name="ollama", available=True, details="Available")

        models = [
            model.get("name", "unknown")
            for model in data.get("models", [])
            if isinstance(model, dict)
        ]
        details = ", ".join(models) if models else "Available"
        return ServiceInfo(name="ollama", available=True, details=details)

    def status(self) -> SystemStatus:
        return SystemStatus(
            cpu=self.cpu(),
            memory=self.memory(),
            disks=self.storage(),
            gpus=self.gpu(),
            network=self.network(),
            services=[self.docker(), self.ollama()],
        )

    def _disk_paths(self) -> list[str]:
        paths: list[str] = []
        for partition in psutil.disk_partitions(all=False):
            if partition.mountpoint and partition.mountpoint not in paths:
                paths.append(partition.mountpoint)
        return paths

    def _ip_addresses(self) -> list[str]:
        addresses: list[str] = []
        for interface_addresses in psutil.net_if_addrs().values():
            for address in interface_addresses:
                if address.family not in (socket.AF_INET, socket.AF_INET6):
                    continue
                ip_address = address.address.split("%", 1)[0]
                if ip_address in {"127.0.0.1", "::1"}:
                    continue
                if ip_address not in addresses:
                    addresses.append(ip_address)
        return addresses

    @staticmethod
    def _gb(value: int | float) -> float:
        return round(float(value) / BYTES_PER_GB, 2)

    @staticmethod
    def _float_or_none(value: str) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _require_psutil() -> None:
        if psutil is None:
            raise RuntimeError(
                "System API requires psutil. Install dependencies with "
                "`pip install -r requirements/base.txt`."
            )
