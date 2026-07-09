"""Architecture-test OCR provider for VisionRuntime."""

from __future__ import annotations

from pathlib import Path

from aegis.vision.models import VisionElement


class StubOCRProvider:
    name = "stub"

    def __init__(self):
        self.last_metadata: dict = {}

    def available(self) -> bool:
        return True

    def languages(self) -> list[str]:
        return []

    def recognize(
        self,
        image_path: str,
        region: dict | None = None,
    ) -> list[VisionElement]:
        self.last_metadata = {
            "warning": "Stub OCR provider is active; no text extraction was performed.",
            "image_exists": Path(image_path).exists(),
            "region": region,
        }
        return []

    def recognize_region(
        self,
        image_path: str,
        region: dict,
    ) -> list[VisionElement]:
        return self.recognize(image_path, region=region)

    def capabilities(self) -> list[str]:
        return ["ocr.stub"]
