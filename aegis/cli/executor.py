from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("execute")
def execute_plan(plan_id: str = typer.Argument(..., metavar="PLAN_ID")):
    """Execute a plan through Agent Executor Runtime."""
    core = AegisCore()
    try:
        result = core.executor_runtime.execute_payload({"plan_id": plan_id})
    except (KeyError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(result))
    if not result.get("success"):
        raise typer.Exit(code=1)


@app.command("dry-run")
def dry_run(plan_id: str = typer.Argument(..., metavar="PLAN_ID")):
    """Print the Observe/Action/Validate shape without executing actions."""
    core = AegisCore()
    try:
        steps = core.executor_runtime.dry_run_payload({"plan_id": plan_id})
    except (KeyError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    for item in steps:
        console.print(f"Step {item['step']}: {item['id']}")
        console.print("Observe")
        console.print("↓")
        console.print("Action")
        console.print(_format_block(item["action"]))
        console.print("↓")
        console.print("Expected validation")
        console.print(_format_block(item["expected_validation"]))


@app.command("validate")
def validate_plan(plan_id: str = typer.Argument(..., metavar="PLAN_ID")):
    """Validate that a plan can be adapted to Executor Runtime."""
    core = AegisCore()
    try:
        result = core.executor_runtime.validate_payload({"plan_id": plan_id})
    except (KeyError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(result))
    if not result.get("success"):
        raise typer.Exit(code=1)


@app.command("execute-file")
def execute_file(path: Path = typer.Argument(..., metavar="PLAN_FILE")):
    """Execute an Executor Runtime plan JSON file."""
    payload = _load_json_file(path)
    core = AegisCore()
    result = core.executor_runtime.execute_payload(payload)
    console.print_json(data=to_plain(result))
    if not result.get("success"):
        raise typer.Exit(code=1)


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        console.print(f"[red]Cannot read plan file:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid plan JSON:[/red] {exc.msg}")
        raise typer.Exit(code=1) from exc

    if not isinstance(payload, dict):
        console.print("[red]Plan file must contain a JSON object.[/red]")
        raise typer.Exit(code=1)
    return payload


def _format_block(value: Any) -> str:
    plain = to_plain(value)
    if plain in (None, {}, []):
        return "  -"
    return json.dumps(plain, ensure_ascii=False, indent=2)
