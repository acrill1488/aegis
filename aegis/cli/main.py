import shutil
import subprocess
import sys
import os

import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

from aegis.vision.screen import capture_screen
from aegis.runtime.manager import RuntimeManager
from aegis.config.runtime_config import get_runtime_profile

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
        r = httpx.get("http://192.168.1.7:11434/api/tags", timeout=30.0, trust_env=False)
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
def models(profile: str = typer.Option("coding", "--profile", "-p")):
    """List available models."""
    runtime = RuntimeManager(profile_name=profile)
    try:
        # Debug information
        console.print(f"[bold yellow]Selected profile:[/bold yellow] {profile}")
        
        # Get profile details for debug info
        from ..config.runtime_config import get_runtime_profile
        profile_config = get_runtime_profile(profile)
        console.print(f"[bold yellow]Base URL:[/bold yellow] {profile_config['base_url']}")
        console.print(f"[bold yellow]Model:[/bold yellow] {profile_config['model']}")
        
        # Make direct request to get debug info about status and response
        import httpx
        url = f"{profile_config['base_url'].rstrip('/')}/api/tags"
        try:
            r = httpx.get(url, timeout=30, trust_env=False)
            console.print(f"[bold yellow]Status Code:[/bold yellow] {r.status_code}")
            response_preview = r.text[:200] + "..." if len(r.text) > 200 else r.text
            console.print(f"[bold yellow]Response preview:[/bold yellow] {response_preview}")
        except Exception as e:
            console.print(f"[bold yellow]Connection Error:[/bold yellow] {e}")
        
        models = runtime.list_models()
        if not models:
            console.print("[bold red]No models found[/bold red]")
            return
        
        table = Table(title="Available Models")
        table.add_column("Model Name")
        
        for model in models:
            table.add_row(model)
        
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error fetching models: {e}[/bold red]")

@app.command()
def chat(prompt: str = typer.Argument(...), 
         model: str = typer.Option(None, "--model", "-m"),
         profile: str = typer.Option("coding", "--profile", "-p")):
    """Chat with AI model."""
    runtime = RuntimeManager(profile_name=profile)
    try:
        if not runtime.is_available():
            console.print("[bold red]Runtime is not available[/bold red]")
            return
            
        response = runtime.chat(model, prompt)
        console.print(f"[bold blue]Model:[/bold blue] {model}")
        console.print(f"[bold green]Response:[/bold green] {response}")
    except Exception as e:
        console.print(f"[bold red]Error during chat: {e}[/bold red]")

@app.command()
def screen():
    """Capture screenshot of the main monitor."""
    try:
        filepath = capture_screen()
        console.print(f"Screenshot saved to: [bold green]{filepath}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error capturing screenshot:[/bold red] {e}")

@app.command()
def version():
    console.print("AEGIS CLI 0.1.0")
if __name__ == "__main__":
    app()
