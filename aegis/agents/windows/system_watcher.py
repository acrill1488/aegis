import socket
from datetime import datetime
from typing import Callable

from aegis.watchers import BaseWatcher

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only in incomplete environments.
    psutil = None


SystemEventCallback = Callable[[str, dict], None]
SYSTEM_WATCHER_TASK_NAME = "system-watcher"


class SystemWatcher(BaseWatcher):
    """Watch local system metrics and mirror them into Live Context."""

    source = "system_watcher"

    def __init__(
        self,
        core,
        interval_seconds: int | float = 2,
        on_event: SystemEventCallback | None = None,
        *,
        cpu_high_percent: float = 90.0,
        memory_high_percent: float = 90.0,
        disk_low_free_percent: float = 10.0,
        disk_low_free_gb: float = 5.0,
        internet_host: str = "1.1.1.1",
        internet_port: int = 443,
        internet_timeout_seconds: float = 1.0,
    ):
        super().__init__(
            id=SYSTEM_WATCHER_TASK_NAME,
            name="System Watcher",
            interval=interval_seconds,
            scheduler=core.scheduler,
            event_bus=core.events,
            live_context=core.live_context,
        )
        self.interval_seconds = interval_seconds
        self.on_event = on_event
        self.cpu_high_percent = cpu_high_percent
        self.memory_high_percent = memory_high_percent
        self.disk_low_free_percent = disk_low_free_percent
        self.disk_low_free_gb = disk_low_free_gb
        self.internet_host = internet_host
        self.internet_port = internet_port
        self.internet_timeout_seconds = internet_timeout_seconds
        self._task_name = SYSTEM_WATCHER_TASK_NAME
        self._running = False
        self._last_metrics: dict | None = None
        self._last_event: dict | None = None
        self._error: str | None = None
        self._cpu_high = False
        self._memory_high = False
        self._disk_low_paths: set[str] = set()
        self._internet_connected: bool | None = None

    def start(self) -> dict:
        _require_psutil()
        if self._running:
            return self.status()

        self.tick()
        self.scheduler.watcher_registry.register(self, replace=True)
        self._running = True
        self._error = None
        super().start()
        return self.status()

    def stop(self) -> None:
        self.scheduler.watcher_registry.unregister(self.id)
        self._running = False
        super().stop()

    def status(self) -> dict:
        scheduler_status = self.scheduler.status()
        task = self.scheduler.registry.get(self._task_name)
        thread_alive = bool(scheduler_status["thread_alive"] and task is not None)
        return {
            "watcher": "system",
            "running": self._running,
            "thread_alive": thread_alive,
            "interval_seconds": self.interval_seconds,
            "last_metrics": self._last_metrics,
            "last_event": self._last_event,
            "error": self._error,
            "scheduler_task": self._task_name if task is not None else None,
        }

    def tick(self) -> None:
        """Run one system metrics check iteration."""
        try:
            metrics = self.snapshot()
            self._set_context(metrics)
            self._publish_threshold_events(metrics)
            self._last_metrics = metrics
            self._error = None
            self.mark_tick_success()
        except Exception as exc:
            self._error = str(exc)
            self.mark_tick_error(exc)
            raise

    def snapshot(self) -> dict:
        _require_psutil()
        return {
            "cpu": self._cpu_snapshot(),
            "memory": self._memory_snapshot(),
            "disk": self._disk_snapshot(),
            "network": self._network_snapshot(),
            "internet": self._internet_snapshot(),
            "timestamp": datetime.now().isoformat(),
        }

    def _cpu_snapshot(self) -> dict:
        return {
            "percent": float(psutil.cpu_percent(interval=None)),
            "cores": int(psutil.cpu_count(logical=False) or 0),
            "logical_cores": int(psutil.cpu_count(logical=True) or 0),
        }

    def _memory_snapshot(self) -> dict:
        memory = psutil.virtual_memory()
        return {
            "total_gb": _gb(memory.total),
            "used_gb": _gb(memory.used),
            "free_gb": _gb(memory.available),
            "percent": float(memory.percent),
        }

    def _disk_snapshot(self) -> dict:
        disks = []
        for partition in psutil.disk_partitions(all=False):
            mountpoint = partition.mountpoint
            if not mountpoint:
                continue
            try:
                usage = psutil.disk_usage(mountpoint)
            except (FileNotFoundError, OSError, PermissionError):
                continue
            disks.append(
                {
                    "path": mountpoint,
                    "total_gb": _gb(usage.total),
                    "used_gb": _gb(usage.used),
                    "free_gb": _gb(usage.free),
                    "percent": float(usage.percent),
                    "free_percent": round(100.0 - float(usage.percent), 2),
                }
            )
        return {"disks": disks}

    def _network_snapshot(self) -> dict:
        counters = psutil.net_io_counters()
        return {
            "hostname": socket.gethostname(),
            "ip_addresses": self._ip_addresses(),
            "bytes_sent": int(counters.bytes_sent),
            "bytes_recv": int(counters.bytes_recv),
            "packets_sent": int(counters.packets_sent),
            "packets_recv": int(counters.packets_recv),
        }

    def _internet_snapshot(self) -> dict:
        connected = self._check_internet()
        return {
            "connected": connected,
            "target": f"{self.internet_host}:{self.internet_port}",
            "timeout_seconds": self.internet_timeout_seconds,
        }

    def _check_internet(self) -> bool:
        try:
            with socket.create_connection(
                (self.internet_host, self.internet_port),
                timeout=self.internet_timeout_seconds,
            ):
                return True
        except OSError:
            return False

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

    def _set_context(self, metrics: dict) -> None:
        ttl_seconds = max(int(float(self.interval_seconds) * 3), 6)
        for key in ("cpu", "memory", "disk", "network", "internet"):
            self.update_context(
                key=f"system.{key}",
                value=metrics[key],
                ttl_seconds=ttl_seconds,
            )

    def _publish_threshold_events(self, metrics: dict) -> None:
        cpu_high = metrics["cpu"]["percent"] >= self.cpu_high_percent
        if cpu_high and not self._cpu_high:
            self._publish_event("system.cpu_high", metrics["cpu"])
        self._cpu_high = cpu_high

        memory_high = metrics["memory"]["percent"] >= self.memory_high_percent
        if memory_high and not self._memory_high:
            self._publish_event("system.memory_high", metrics["memory"])
        self._memory_high = memory_high

        internet_connected = bool(metrics["internet"]["connected"])
        if self._internet_connected is not None:
            if not internet_connected and self._internet_connected:
                self._publish_event("system.internet_lost", metrics["internet"])
            if internet_connected and not self._internet_connected:
                self._publish_event("system.internet_restored", metrics["internet"])
        self._internet_connected = internet_connected

        low_paths = {
            disk["path"]
            for disk in metrics["disk"]["disks"]
            if (
                disk["free_percent"] <= self.disk_low_free_percent
                or disk["free_gb"] <= self.disk_low_free_gb
            )
        }
        for disk in metrics["disk"]["disks"]:
            path = disk["path"]
            if path in low_paths and path not in self._disk_low_paths:
                self._publish_event("system.disk_low", disk)
        self._disk_low_paths = low_paths

    def _publish_event(self, event_type: str, payload: dict) -> None:
        event_payload = dict(payload)
        event_payload["event"] = event_type
        event_payload["timestamp"] = datetime.now().isoformat()

        self.publish(event_type, event_payload)
        self.update_context(
            key="system.last_event",
            value=event_payload,
            ttl_seconds=3600,
        )
        self._last_event = event_payload

        if self.on_event is not None:
            self.on_event(event_type, event_payload)


def _gb(value: int | float) -> float:
    return round(float(value) / (1024**3), 2)


def _require_psutil() -> None:
    if psutil is None:
        raise RuntimeError(
            "SystemWatcher requires psutil. Install dependencies with "
            "`pip install -r requirements/base.txt`."
        )
