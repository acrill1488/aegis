import shutil
import subprocess
import sys

import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer()
console = Console()


def check_command(command: str) -> bool:
    return shutil.which(command) is not None


@app.command()
def doctor():
    console.print(Panel("AEGIS System Doctor"))

    table = Table(title="System Check Results")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row("Python Version", "✅", sys.version.split()[0])
    table.add_row("Git", "✅" if check_command("git") else "❌", "git")
    table.add_row("Node.js", "✅" if check_command("node") else "❌", "node")

    npm_ok = check_command("npm") or check_command("npm.cmd")
    table.add_row("npm", "✅" if npm_ok else "❌", "npm")

    try:
        r = httpx.get("http://192.168.1.7:11434/api/tags", timeout=30.0)
        if r.status_code == 200:
            data = r.json()
            models = data.get("models", [])
            model_names = ", ".join([m.get("name", "unknown") for m in models]) or "No models"
            table.add_row("Ollama API", "✅", "Available")
            table.add_row("Ollama Models", "✅", model_names)
        elif r.status_code == 503:
            table.add_row("Ollama API", "⚠️", "Busy / loading model")
            table.add_row("Ollama Models", "⚠️", "Cannot check while busy")
        else:
            table.add_row("Ollama API", "❌", f"Status {r.status_code}")
            table.add_row("Ollama Models", "⚠️", "Cannot check models")
    except Exception as e:
        table.add_row("Ollama API", "❌", str(e))
        table.add_row("Ollama Models", "⚠️", "Cannot check models")

    console.print(table)

@app.command()
def version():
    console.print("AEGIS CLI 0.1.0")
if __name__ == "__main__":
    app()