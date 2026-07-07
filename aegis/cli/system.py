import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aegis.system import (
    CPUInfo,
    DiskInfo,
    GPUInfo,
    MemoryInfo,
    NetworkInfo,
    ServiceInfo,
    SystemAPI,
)

app = typer.Typer()
console = Console()


@app.command()
def cpu():
    """Show CPU status."""
    info = _call(lambda: _api().cpu())
    _render_cpu(info)


@app.command()
def memory():
    """Show memory status."""
    info = _call(lambda: _api().memory())
    _render_memory(info)


@app.command()
def gpu():
    """Show GPU status."""
    _render_gpus(_api().gpu())


@app.command()
def storage():
    """Show storage status."""
    disks = _call(lambda: _api().storage())
    _render_disks(disks)


@app.command()
def network():
    """Show network status."""
    info = _call(lambda: _api().network())
    _render_network(info)


@app.command()
def status():
    """Show full system status."""
    system_status = _call(lambda: _api().status())
    console.print(Panel("AEGIS System Status"))
    _render_cpu(system_status.cpu)
    _render_memory(system_status.memory)
    _render_disks(system_status.disks)
    _render_gpus(system_status.gpus)
    _render_network(system_status.network)
    _render_services(system_status.services)


def _api() -> SystemAPI:
    return SystemAPI()


def _call(action):
    try:
        return action()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _render_cpu(info: CPUInfo) -> None:
    table = Table(title="CPU")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Load", f"{info.percent:.1f}%")
    table.add_row("Cores", str(info.cores))
    table.add_row("Logical cores", str(info.logical_cores))
    console.print(table)


def _render_memory(info: MemoryInfo) -> None:
    table = Table(title="Memory")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Total", f"{info.total_gb:.2f} GB")
    table.add_row("Used", f"{info.used_gb:.2f} GB")
    table.add_row("Free", f"{info.free_gb:.2f} GB")
    table.add_row("Load", f"{info.percent:.1f}%")
    console.print(table)


def _render_disks(disks: list[DiskInfo]) -> None:
    table = Table(title="Storage")
    table.add_column("Path")
    table.add_column("Total")
    table.add_column("Used")
    table.add_column("Free")
    table.add_column("Load")

    if not disks:
        table.add_row("-", "-", "-", "-", "No disks found")
    for disk in disks:
        table.add_row(
            disk.path,
            f"{disk.total_gb:.2f} GB",
            f"{disk.used_gb:.2f} GB",
            f"{disk.free_gb:.2f} GB",
            f"{disk.percent:.1f}%",
        )
    console.print(table)


def _render_gpus(gpus: list[GPUInfo]) -> None:
    table = Table(title="GPU")
    table.add_column("Name")
    table.add_column("Load")
    table.add_column("VRAM")
    table.add_column("Temperature")

    if not gpus:
        table.add_row("-", "-", "-", "No NVIDIA GPU data")
    for gpu_info in gpus:
        table.add_row(
            gpu_info.name,
            _percent(gpu_info.load_percent),
            _vram(gpu_info),
            _temperature(gpu_info.temperature_c),
        )
    console.print(table)


def _render_network(info: NetworkInfo) -> None:
    table = Table(title="Network")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Connected", _status(info.connected))
    table.add_row("Hostname", info.hostname)
    table.add_row("IP addresses", ", ".join(info.ip_addresses) or "-")
    console.print(table)


def _render_services(services: list[ServiceInfo]) -> None:
    table = Table(title="Services")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Details")

    for service in services:
        table.add_row(
            service.name,
            _status(service.available),
            service.details or "-",
        )
    console.print(table)


def _status(available: bool) -> str:
    return "[green]available[/green]" if available else "[red]unavailable[/red]"


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def _temperature(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} C"


def _vram(gpu_info: GPUInfo) -> str:
    if gpu_info.memory_used_mb is None or gpu_info.memory_total_mb is None:
        return "-"
    free = (
        f", {gpu_info.memory_free_mb:.0f} MB free"
        if gpu_info.memory_free_mb is not None
        else ""
    )
    return f"{gpu_info.memory_used_mb:.0f}/{gpu_info.memory_total_mb:.0f} MB{free}"
