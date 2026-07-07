import json

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()


@app.command()
def publish(
    event_type: str = typer.Argument(..., metavar="TYPE"),
    source: str = typer.Option(..., "--source", "-s"),
    payload_json: str = typer.Option("{}", "--payload-json"),
):
    """Publish an AEGIS event."""
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid --payload-json:[/red] {exc.msg}")
        console.print('[yellow]Example:[/yellow] --payload-json "{\\"key\\": \\"value\\"}"')
        raise typer.Exit(code=1)

    if not isinstance(payload, dict):
        console.print("[red]Payload JSON must be an object.[/red]")
        raise typer.Exit(code=1)

    core = AegisCore()
    receipt = core.events.publish(event_type, source, payload)
    console.print(
        f"[green]Published event[/green] {receipt.event_id} "
        f"(delivered={receipt.delivered}, failed={receipt.failed})"
    )


@app.command()
def history(limit: int = typer.Option(50, "--limit", "-n")):
    """Show recent AEGIS events."""
    core = AegisCore()
    events = core.events.history(limit=limit)

    table = Table(title="Event History")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Source")
    table.add_column("Created")
    table.add_column("Payload")

    for event in events:
        table.add_row(
            event.id,
            event.type,
            event.source,
            event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            json.dumps(event.payload, ensure_ascii=False),
        )

    console.print(table)
