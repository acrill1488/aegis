from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from aegis.ocr import OCRRuntime


@pytest.mark.acceptance
@pytest.mark.external
def test_unlimited_ocr_real_image_acceptance(tmp_path):
    if os.getenv("AEGIS_RUN_UNLIMITED_OCR_ACCEPTANCE") != "1":
        pytest.skip("Set AEGIS_RUN_UNLIMITED_OCR_ACCEPTANCE=1 to run real Unlimited-OCR acceptance.")

    configured = os.getenv("AEGIS_UNLIMITED_OCR_ACCEPTANCE_IMAGE", r"C:\Users\MK\Downloads\IMG_4728_1024.png")
    image_path = Path(configured)
    if not image_path.exists():
        pytest.fail(f"Required real acceptance image not found: {image_path}")

    runtime = OCRRuntime()
    result = runtime.recognize_image(
        image_path,
        provider="unlimited",
        language="auto",
        options={"output_dir": str(tmp_path), "greenboost": True},
    )

    assert result.provider == "unlimited"
    assert result.errors == []
    assert len(result.pages) > 0
    assert len(result.blocks) > 0
    assert len(result.text.strip()) > 0
    assert result.metadata["recognition_valid"] is True
    assert result.metadata["visible_text_length"] > 0
    normalized = " ".join(result.text.lower().replace("ё", "е").split())
    expected_fragments = (
        "просроченная задолженность",
        "майрест",
        "3 000 000",
        "1 799 206",
        "256 033",
    )
    assert sum(fragment in normalized for fragment in expected_fragments) >= 2
    assert result.metadata.get("last_inference_peak_vram_mb") is not None
    assert result.metadata["greenboost_enabled"] is True
    assert result.metadata["selected_profile"] == "ocr_rtx3050"
    assert result.metadata["attempts"]
    assert result.metadata["vram_stages"]
    artifact_paths = [
        artifact["path"]
        for artifact in result.artifacts
        if isinstance(artifact, dict) and artifact.get("path")
    ]
    assert any(path.endswith(".txt") for path in artifact_paths)
    assert any(path.endswith(".json") for path in artifact_paths)
    assert any(path.endswith("document.json") for path in artifact_paths)


@pytest.mark.acceptance
@pytest.mark.external
def test_unlimited_ocr_synthetic_smoke(tmp_path):
    if os.getenv("AEGIS_RUN_UNLIMITED_OCR_SMOKE") != "1":
        pytest.skip("Set AEGIS_RUN_UNLIMITED_OCR_SMOKE=1 to run the synthetic smoke test.")
    image_path = tmp_path / "synthetic-smoke.png"
    image = Image.new("RGB", (640, 220), "white")
    ImageDraw.Draw(image).text((40, 80), "AEGIS Unlimited OCR smoke", fill="black")
    image.save(image_path)
    result = OCRRuntime().recognize_image(image_path, provider="unlimited", options={"output_dir": str(tmp_path)})
    assert not result.errors and result.pages and result.blocks and result.text.strip()
    assert result.metadata["recognition_valid"] is True
