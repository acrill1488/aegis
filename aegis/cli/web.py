"""CLI commands for web functionality."""

import typer
from typing import Optional
from aegis.web.browser import WebBrowser

app = typer.Typer(name="web", help="Web browser commands")

@app.command("fetch")
def fetch_url(url: str):
    """Fetch a URL and display its content."""
    # We need to access the core instance to initialize WebBrowser
    from aegis.core.core import AegisCore
    
    try:
        core = AegisCore()
        browser = WebBrowser(core)
        result = browser.fetch_url(url)
        
        typer.echo(f"URL: {result['url']}")
        if result.get('final_url') and result['final_url'] != url:
            typer.echo(f"Final URL: {result['final_url']}")
        typer.echo(f"Status Code: {result['status_code']}")
        typer.echo(f"Title: {result['title']}")
        typer.echo(f"Error: {result['error']}")
        typer.echo("Preview:")
        typer.echo(result['text_preview'][:500] + "..." if result['text_preview'] and len(result['text_preview']) > 500 else result['text_preview'])
    except Exception as e:
        typer.echo(f"Error: {str(e)}")

@app.command("summarize")
def summarize_url(url: str, profile: Optional[str] = "general"):
    """Summarize a URL."""
    # We need to access the core instance to initialize WebBrowser
    from aegis.core.core import AegisCore
    
    try:
        core = AegisCore()
        browser = WebBrowser(core)
        summary = browser.summarize_url(url, profile)
        typer.echo(summary)
    except Exception as e:
        typer.echo(f"Error: {str(e)}")