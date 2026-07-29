"""GreenBoost system resource commands."""

import json
import os

import typer
from rich.console import Console

from .client import GreenBoostClient
from .errors import GreenBoostError
from .runtime import GreenBoostRuntime
from .probes import ResourceProbe
from aegis.config.services import get_greenboost_config

app = typer.Typer()
console = Console()


@app.command("serve")
def serve() -> None:
    """Run the configured authenticated GBIP observation service."""
    config = get_greenboost_config()
    if not config.server.enabled:
        raise typer.BadParameter("greenboost.server.enabled must be true")
    if config.server.host in {"0.0.0.0", "::"}:
        raise typer.BadParameter(
            "greenboost.server.host must be a specific bind address"
        )
    if not os.environ.get(config.server.token_env):
        raise typer.BadParameter(f"{config.server.token_env} is required")
    import uvicorn

    uvicorn.run(
        "aegis.greenboost.server.app:app",
        host=config.server.host,
        port=config.server.port,
        access_log=False,
    )


def _print(operation: str) -> None:
    try:
        with GreenBoostClient() as client:
            value = getattr(client, operation)()
        if isinstance(value, tuple):
            payload = [item.model_dump(mode="json") for item in value]
        else:
            payload = value.model_dump(mode="json")
        console.print_json(json.dumps(payload))
    except GreenBoostError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command("health")
def health() -> None:
    """Check GreenBoost through the public GBIP client."""
    _print("health")


@app.command("discover")
def discover() -> None:
    """List nodes discovered by GreenBoost through GBIP."""
    _print("discover")


@app.command("snapshot")
def snapshot(
    remote: bool = typer.Option(
        False, "--remote", help="Fetch only the RFC-055 remote snapshot."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON only."),
) -> None:
    """Collect a one-shot ResourceSnapshot without changing runtime state."""
    if remote:
        _print("snapshot")
        return
    payload = ResourceProbe().collect().model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    typer.echo(f"node: {payload['node']['id']}")
    typer.echo(f"gpus: {len(payload['gpus'])}")
    typer.echo(f"services: {len(payload['services'])}")
    typer.echo(f"models: {len(payload['models'])}")
    typer.echo(f"warnings: {len(payload['probe_warnings'])}")


@app.command("probes")
def probes(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON only."),
) -> None:
    """Show the status of each configured one-shot resource probe."""
    results = ResourceProbe().results()
    payload = [
        result.model_dump(mode="json", by_alias=True, exclude={"remote_snapshot"})
        for result in results
    ]
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    for result in results:
        typer.echo(f"{result.probe_name}: {result.status.value}")


@app.command("doctor")
def doctor() -> None:
    console.print_json(json.dumps(GreenBoostRuntime().doctor()))


@app.command("status")
def status() -> None:
    console.print_json(json.dumps(GreenBoostRuntime().snapshot()))


@app.command("plan")
def plan(task: str = typer.Option(..., "--task")) -> None:
    console.print_json(json.dumps(GreenBoostRuntime().plan(task)))
