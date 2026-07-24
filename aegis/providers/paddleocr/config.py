"""Configuration for the optional PaddleOCR provider."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from aegis.config.services import load_services_config


@dataclass(frozen=True)
class PaddleOCRConfig:
    enabled: bool = True
    device: str = "auto"
    language: str = "en"
    use_angle_cls: bool = True
    confidence_threshold: float = 0.5
    timeout_seconds: float = 120.0
    max_image_size: int = 4096

    def __post_init__(self) -> None:
        if self.device not in {"auto", "cpu", "gpu"}:
            raise ValueError("PaddleOCR device must be one of: auto, cpu, gpu")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("PaddleOCR confidence_threshold must be between 0 and 1")
        if self.timeout_seconds <= 0:
            raise ValueError("PaddleOCR timeout_seconds must be greater than zero")
        if self.max_image_size <= 0:
            raise ValueError("PaddleOCR max_image_size must be greater than zero")

    @classmethod
    def load(cls, config_path: str | Path | None = None, **overrides: Any) -> "PaddleOCRConfig":
        services = load_services_config(config_path)
        section = services.data.get("ocr", {}).get("providers", {}).get("paddleocr", {})
        if not isinstance(section, dict):
            raise ValueError("ocr.providers.paddleocr must be a mapping")
        allowed = {item.name for item in fields(cls)}
        unknown = set(section) - allowed
        if unknown:
            raise ValueError(f"Unknown PaddleOCR configuration fields: {', '.join(sorted(unknown))}")
        values = {**section, **{key: value for key, value in overrides.items() if value is not None}}
        return cls(**values)

    def with_overrides(self, **values: Any) -> "PaddleOCRConfig":
        return replace(self, **{key: value for key, value in values.items() if value is not None})

