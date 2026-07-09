"""Unlimited OCR provider backed by HuggingFace Transformers."""

from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path
from typing import Any

from aegis.vision.models import VisionElement


DEFAULT_MODEL_ID = "stepfun-ai/GOT-OCR-2.0-hf"


class UnlimitedOCRProvider:
    name = "unlimited"
    display_name = "Unlimited OCR"

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id or os.getenv("AEGIS_UNLIMITED_OCR_MODEL", DEFAULT_MODEL_ID)
        self.last_metadata: dict[str, Any] = {}
        self._pipeline = None

    def available(self) -> bool:
        if os.getenv("AEGIS_UNLIMITED_OCR_DISABLED", "").lower() in {"1", "true", "yes"}:
            self.last_metadata = {"available": False, "reason": "disabled_by_environment"}
            return False
        missing = [
            package
            for package in ("transformers", "PIL")
            if importlib.util.find_spec(package) is None
        ]
        if missing:
            self.last_metadata = {
                "available": False,
                "reason": "missing_dependencies",
                "missing": missing,
            }
            return False
        self.last_metadata = {"available": True, "model_id": self.model_id}
        return True

    def languages(self) -> list[str]:
        return ["auto"]

    def recognize(
        self,
        image_path: str,
        region: dict | None = None,
    ) -> list[VisionElement]:
        if region is not None:
            return self.recognize_region(image_path, region)

        target = Path(image_path)
        if not target.exists():
            raise FileNotFoundError(str(target))

        pipeline = self._load_pipeline()
        raw_result = pipeline(str(target))
        text = self._extract_text(raw_result)
        self.last_metadata = {
            "provider": self.name,
            "model_id": self.model_id,
            "raw_result_type": type(raw_result).__name__,
        }
        if not text.strip():
            return []
        return [
            VisionElement(
                type="text",
                text=text,
                confidence=0.0,
                source=self.name,
                metadata={"model_id": self.model_id},
            )
        ]

    def recognize_region(
        self,
        image_path: str,
        region: dict,
    ) -> list[VisionElement]:
        from PIL import Image

        x = int(region.get("x", 0))
        y = int(region.get("y", 0))
        width = int(region.get("width", 0))
        height = int(region.get("height", 0))
        if width <= 0 or height <= 0:
            raise ValueError("region width and height must be positive")

        with Image.open(image_path) as image:
            crop = image.crop((x, y, x + width, y + height))
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                crop_path = Path(temp_file.name)
            try:
                crop.save(crop_path)
                elements = self.recognize(str(crop_path))
            finally:
                crop_path.unlink(missing_ok=True)

        for element in elements:
            element.metadata = {**element.metadata, "region": dict(region)}
        return elements

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        from transformers import pipeline

        self._pipeline = pipeline(
            "image-to-text",
            model=self.model_id,
            trust_remote_code=True,
        )
        return self._pipeline

    def _extract_text(self, raw_result) -> str:
        if isinstance(raw_result, str):
            return raw_result
        if isinstance(raw_result, dict):
            return str(
                raw_result.get("generated_text")
                or raw_result.get("text")
                or raw_result.get("label")
                or ""
            )
        if isinstance(raw_result, list):
            texts = [self._extract_text(item) for item in raw_result]
            return "\n".join(text for text in texts if text.strip())
        return str(raw_result or "")
