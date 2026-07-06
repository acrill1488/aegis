import typer

from aegis.router.capability import CapabilityRouter

app = typer.Typer()
router = CapabilityRouter()

@app.command("detect")
def detect_command(text: str = typer.Argument(...)):
    """Detect the capability from text."""
    capability = router.detect(text)
    print(capability)