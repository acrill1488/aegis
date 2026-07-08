from __future__ import annotations

from .base import BaseInferenceProvider
from .ollama import OllamaProvider

__all__ = ["BaseInferenceProvider", "OllamaProvider"]
