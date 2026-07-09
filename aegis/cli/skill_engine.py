from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("list")
def list_skills():
    """List YAML skill graph definitions."""
    runtime = AegisCore().skill_engine
    table = Table(title="Skill Graphs")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Nodes")
    for skill in runtime.skills.list():
        table.add_row(skill.id, skill.name, skill.version, str(len(skill.nodes)))
    console.print(table)


@app.command("show")
def show_skill(skill_id: str = typer.Argument(..., metavar="SKILL_ID")):
    """Show a YAML skill graph definition."""
    runtime = AegisCore().skill_engine
    skill = runtime.skills.get(skill_id)
    if skill is None:
        console.print(f"[red]Skill not found: {skill_id}[/red]")
        raise typer.Exit(code=1)
    console.print(JSON.from_data(to_plain(skill)))


@app.command("validate")
def validate_skill(skill_id: str = typer.Argument(..., metavar="SKILL_ID")):
    """Validate a YAML skill graph definition."""
    runtime = AegisCore().skill_engine
    try:
        result = runtime.validate(skill_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(JSON.from_data(to_plain(result)))
    if not result["success"]:
        raise typer.Exit(code=1)


@app.command("dry-run")
def dry_run_skill(
    skill_id: str = typer.Argument(..., metavar="SKILL_ID"),
    extra_inputs: list[str] = typer.Argument(None, metavar="KEY=VALUE"),
    input_json: str = typer.Option("{}", "--input-json"),
    input_file: Path | None = typer.Option(None, "--input-file"),
    query: str | None = typer.Option(None, "--query"),
):
    """Render and validate a skill graph run without executing actions."""
    inputs = _load_inputs(
        input_json=input_json,
        input_file=input_file,
        query=query,
        extra_inputs=extra_inputs,
    )
    _print_run_result(AegisCore().skill_engine.dry_run(skill_id, inputs))


@app.command("run")
def run_skill(
    skill_id: str = typer.Argument(..., metavar="SKILL_ID"),
    extra_inputs: list[str] = typer.Argument(None, metavar="KEY=VALUE"),
    input_json: str = typer.Option("{}", "--input-json"),
    input_file: Path | None = typer.Option(None, "--input-file"),
    query: str | None = typer.Option(None, "--query"),
):
    """Run a YAML skill graph through AEGIS runtimes."""
    result = AegisCore().skill_engine.run(
        skill_id,
        _load_inputs(
            input_json=input_json,
            input_file=input_file,
            query=query,
            extra_inputs=extra_inputs,
        ),
    )
    _print_run_result(result)
    if not result.success:
        raise typer.Exit(code=1)


def _load_inputs(
    input_json: str,
    input_file: Path | None,
    query: str | None = None,
    extra_inputs: list[str] | None = None,
) -> dict:
    if input_file is not None:
        try:
            input_text = input_file.read_text(encoding="utf-8-sig")
        except OSError as exc:
            console.print(f"[red]Cannot read --input-file:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        inputs = _parse_inputs(input_text, source=f"--input-file {input_file}")
    else:
        inputs = _parse_inputs(input_json, source="--input-json")
    if query is not None:
        inputs["query"] = query
    for item in extra_inputs or []:
        key, separator, value = item.partition("=")
        if not separator or not key.strip():
            console.print(f"[red]Invalid input argument:[/red] {item}")
            console.print("[yellow]Use KEY=VALUE, for example query=AEGIS.[/yellow]")
            raise typer.Exit(code=1)
        inputs[key.strip()] = value
    return inputs


def _parse_inputs(input_json: str, *, source: str) -> dict:
    try:
        inputs = json.loads(input_json)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid JSON in {source}:[/red] {exc.msg}")
        console.print(f"[yellow]Location:[/yellow] line {exc.lineno}, column {exc.colno}")
        raise typer.Exit(code=1) from exc
    if not isinstance(inputs, dict):
        console.print(f"[red]Inputs from {source} must be a JSON object.[/red]")
        raise typer.Exit(code=1)
    return inputs


def _print_run_result(result) -> None:
    console.print(json.dumps(to_plain(result), ensure_ascii=True, indent=2))
