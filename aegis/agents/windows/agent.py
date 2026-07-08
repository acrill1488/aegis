import socket

from aegis.agents.runtime import (
    AgentCapability,
    AgentDescriptor,
    AgentHealth,
    AgentHealthState,
    AgentInvocation,
    AgentInvocationResult,
    BaseAgent,
)
from aegis.serialization import to_plain

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only in incomplete environments.
    psutil = None


class WindowsAgent(BaseAgent):
    """Local Windows capability provider for system state and live context."""

    def __init__(self, core, machine_id: str | None = None):
        self.core = core
        self.descriptor = AgentDescriptor(
            id="windows-agent",
            name="Windows Agent",
            version="1",
            machine_id=machine_id or socket.gethostname(),
            capabilities=[
                AgentCapability(
                    id="windows.process.list",
                    description="List local Windows processes.",
                    permissions=["windows.process.read"],
                    metadata={"sensitivity": "local_system_state"},
                ),
                AgentCapability(
                    id="windows.system.status",
                    description="Read local CPU, RAM, GPU, disk, network, and service status.",
                    permissions=["windows.system.read"],
                    metadata={"sensitivity": "local_system_state"},
                ),
                AgentCapability(
                    id="windows.context.snapshot",
                    description="Read the current AEGIS live context snapshot.",
                    permissions=["live_context.read"],
                    metadata={"sensitivity": "local_context"},
                ),
            ],
            health=AgentHealth(AgentHealthState.healthy, message="Ready"),
            metadata={"runtime": "builtin", "platform": "windows"},
        )

    def invoke(self, invocation: AgentInvocation) -> AgentInvocationResult:
        handlers = {
            "windows.process.list": self._process_list,
            "windows.system.status": self._system_status,
            "windows.context.snapshot": self._context_snapshot,
        }
        handler = handlers.get(invocation.capability_id)
        if handler is None:
            return AgentInvocationResult(
                success=False,
                error=f"Unsupported capability: {invocation.capability_id}",
            )

        return AgentInvocationResult(success=True, output=handler())

    def _process_list(self) -> dict:
        _require_psutil()
        processes = []
        for process in psutil.process_iter(
            attrs=["pid", "name", "username", "cpu_percent", "memory_info"]
        ):
            try:
                info = process.info
                memory_info = info.get("memory_info")
                processes.append(
                    {
                        "pid": int(info["pid"]),
                        "name": info.get("name") or "",
                        "username": info.get("username"),
                        "cpu_percent": float(info.get("cpu_percent") or 0.0),
                        "memory_mb": _memory_mb(
                            getattr(memory_info, "rss", 0) if memory_info else 0
                        ),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return {"processes": processes}

    def _system_status(self) -> dict:
        return {"status": to_plain(self.core.system.status())}

    def _context_snapshot(self) -> dict:
        snapshot = self.core.live_context.snapshot()
        return {"entries": [to_plain(entry) for entry in snapshot.entries]}


def _memory_mb(value: int | float) -> float:
    return round(float(value) / (1024**2), 2)


def _require_psutil() -> None:
    if psutil is None:
        raise RuntimeError(
            "WindowsAgent requires psutil. Install dependencies with "
            "`pip install -r requirements/base.txt`."
        )

