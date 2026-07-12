from __future__ import annotations

import os
from pathlib import Path

import pytest

from aegis.core.core import AegisCore


pytestmark = [pytest.mark.acceptance, pytest.mark.external]


@pytest.mark.skipif(
    os.environ.get("AEGIS_RUN_COMFYUI_ACCEPTANCE") != "1",
    reason="Set AEGIS_RUN_COMFYUI_ACCEPTANCE=1 to run external ComfyUI acceptance.",
)
def test_comfyui_image_generation_acceptance_creates_real_png():
    core = AegisCore()
    runtime = core.image_generation
    lifecycle_events: list[str] = []
    for event_type in (
        "image.generation.started",
        "image.generation.completed",
        "image.generation.failed",
        "image.artifact.saved",
    ):
        core.events.subscribe(event_type, lambda event, event_type=event_type: lifecycle_events.append(event_type))

    provider_report = {item["name"]: item for item in runtime.providers()}

    assert provider_report["comfyui"]["available"] is True
    assert provider_report["comfyui"]["default"] is True

    result = runtime.generate(
        "neo tribal tattoo sketch, black ink, clean white background",
        provider="comfyui",
        workflow="default",
        width=512,
        height=512,
        steps=8,
        output_dir=str(Path(r"F:\AI_WORKSPACE\images\generated")),
        metadata={"acceptance": "image-generation"},
    )

    assert result.success is True, result.error
    assert result.provider == "comfyui"
    assert result.provider != "stub"
    assert result.workflow == "default"
    assert result.seed is not None
    assert result.image_paths
    assert result.artifacts
    assert result.artifacts[0]["provider"] == "comfyui"
    assert "image.generation.completed" in lifecycle_events
    assert "image.artifact.saved" in lifecycle_events
    assert "image.generation.failed" not in lifecycle_events
    output_path = Path(result.image_paths[0])
    assert output_path.exists()
    assert output_path.suffix.lower() == ".png"
    assert output_path.stat().st_size > 0
    assert output_path.read_bytes().startswith(b"\x89PNG")
