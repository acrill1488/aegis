import importlib.util
import json
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.json import JSON

from aegis.core.core import AegisCore
from aegis.live.models import ContextEntry, ContextSnapshot
from aegis.live.watchers import WorkspaceWatcher

app = typer.Typer()
console = Console()
DEFAULT_WORKSPACE_PATH = r"F:\AI_WORKSPACE"


def _entry_to_dict(entry: ContextEntry) -> dict:
    return {
        "key": entry.key,
        "value": entry.value,
        "source": entry.source,
        "updated_at": entry.updated_at.isoformat(),
        "ttl_seconds": entry.ttl_seconds,
        "metadata": entry.metadata,
    }


def _snapshot_to_dict(snapshot: ContextSnapshot) -> dict:
    return {
        "entries": [_entry_to_dict(entry) for entry in snapshot.entries],
        "created_at": snapshot.created_at.isoformat(),
        "metadata": snapshot.metadata,
    }


def _print_json(data: dict | list) -> None:
    console.print(JSON.from_data(data))


def _parse_json_object(raw_json: str, option_name: str) -> dict:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid {option_name}:[/red] {exc.msg}")
        raise typer.Exit(code=1)

    if not isinstance(data, dict):
        console.print(f"[red]{option_name} must be a JSON object.[/red]")
        raise typer.Exit(code=1)
    return data


def _read_json_object(
    *,
    json_value: str,
    json_option_name: str,
    file_path: Path | None,
    file_option_name: str,
) -> dict:
    if file_path is None:
        return _parse_json_object(json_value, json_option_name)

    try:
        raw_json = file_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        console.print(f"[red]Cannot read {file_option_name}[/red] {file_path}: {exc}")
        raise typer.Exit(code=1)

    return _parse_json_object(raw_json, f"{file_option_name} {file_path}")


@app.command("set")
def set_context(
    key: str = typer.Argument(..., metavar="KEY"),
    json_value: str = typer.Option("{}", "--value-json", "--json"),
    value_file: Path | None = typer.Option(None, "--value-file"),
    source: str = typer.Option(..., "--source"),
    ttl_seconds: int | None = typer.Option(None, "--ttl-seconds"),
    metadata_json: str = typer.Option("{}", "--metadata-json"),
    metadata_file: Path | None = typer.Option(None, "--metadata-file"),
):
    """Set a live context entry."""
    value = _read_json_object(
        json_value=json_value,
        json_option_name="--value-json/--json",
        file_path=value_file,
        file_option_name="--value-file",
    )
    metadata = _read_json_object(
        json_value=metadata_json,
        json_option_name="--metadata-json",
        file_path=metadata_file,
        file_option_name="--metadata-file",
    )

    core = AegisCore()
    entry = core.live_context.set(
        key=key,
        value=value,
        source=source,
        ttl_seconds=ttl_seconds,
        metadata=metadata,
    )
    _print_json(_entry_to_dict(entry))


@app.command("get")
def get_context(key: str = typer.Argument(..., metavar="KEY")):
    """Get a live context entry."""
    core = AegisCore()
    entry = core.live_context.get(key)
    if entry is None:
        raise typer.Exit(code=1)
    _print_json(_entry_to_dict(entry))


@app.command("list")
def list_context(prefix: str | None = typer.Option(None, "--prefix")):
    """List live context entries."""
    core = AegisCore()
    entries = core.live_context.list(prefix=prefix)
    _print_json([_entry_to_dict(entry) for entry in entries])


@app.command("snapshot")
def snapshot_context(prefix: str | None = typer.Option(None, "--prefix")):
    """Create a live context snapshot."""
    core = AegisCore()
    snapshot = core.live_context.snapshot(prefix=prefix)
    _print_json(_snapshot_to_dict(snapshot))


@app.command("delete")
def delete_context(key: str = typer.Argument(..., metavar="KEY")):
    """Delete a live context entry."""
    core = AegisCore()
    deleted = core.live_context.delete(key)
    _print_json({"key": key, "deleted": deleted})


@app.command("prune")
def prune_context():
    """Remove expired live context entries."""
    core = AegisCore()
    pruned = core.live_context.prune_expired()
    _print_json({"pruned": pruned})


@app.command("watch-workspace")
def watch_workspace(
    path: str = typer.Option(DEFAULT_WORKSPACE_PATH, "--path"),
):
    """Watch workspace changes in the foreground."""
    core = AegisCore()
    watcher = WorkspaceWatcher(
        core,
        path=path,
        on_event=lambda message, _: console.print(message),
    )

    try:
        watcher.start()
    except (FileNotFoundError, NotADirectoryError, RuntimeError) as exc:
        console.print(f"[red]Cannot start workspace watcher:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"Watching workspace: {watcher.path}")
    console.print("Press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("[yellow]Stopping workspace watcher...[/yellow]")
    finally:
        watcher.stop()


@app.command("workspace-status")
def workspace_status(
    path: str = typer.Option(DEFAULT_WORKSPACE_PATH, "--path"),
):
    """Show workspace watcher context status."""
    core = AegisCore()
    root = core.live_context.get("workspace.root")
    last_event = core.live_context.get("workspace.last_event")
    watcher = WorkspaceWatcher(core, path=path)
    watched_path = Path(path)
    event_file = Path(getattr(core.events, "_history_file"))
    context_file = Path(core.live_context.path)

    data = watcher.status()
    data["status_note"] = (
        "running=false only means this CLI command did not start a watcher; "
        "foreground watcher may be running in another process."
    )
    data["checks"] = {
        "exists": watched_path.exists(),
        "is_dir": watched_path.is_dir(),
        "watchdog_installed": importlib.util.find_spec("watchdog") is not None,
        "event_file_path": str(event_file),
        "event_file_exists": event_file.exists(),
        "context_file_path": str(context_file),
        "context_file_exists": context_file.exists(),
    }
    data["context"] = {
        "workspace.root": _entry_to_dict(root) if root is not None else None,
        "workspace.last_event": (
            _entry_to_dict(last_event) if last_event is not None else None
        ),
    }
    _print_json(data)
