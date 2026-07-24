"""Configuration for the optional FlagEmbedding BGE-M3 adapter."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from aegis.config.services import load_services_config


@dataclass(frozen=True)
class BGEM3Config:
    enabled: bool = True
    model_name: str = "BAAI/bge-m3"
    device: str = "auto"
    batch_size: int = 4
    normalize_embeddings: bool = True
    max_length: int = 8192
    use_fp16: bool = True
    timeout_seconds: float = 300.0
    cache_dir: str | None = None
    trust_remote_code: bool = False

    def __post_init__(self) -> None:
        if self.device not in {"auto", "cpu", "gpu"}:
            raise ValueError("BGE-M3 device must be one of: auto, cpu, gpu")
        if self.batch_size <= 0 or self.max_length <= 0 or self.timeout_seconds <= 0:
            raise ValueError("BGE-M3 batch_size, max_length and timeout_seconds must be positive")

    @classmethod
    def load(cls, config_path: str | Path | None = None, **overrides: Any) -> "BGEM3Config":
        config = load_services_config(config_path)
        embeddings = config.data.get("embeddings", {})
        if not isinstance(embeddings, dict) or not isinstance(embeddings.get("providers", {}), dict):
            raise ValueError("embeddings and embeddings.providers must be mappings")
        section = embeddings.get("providers", {}).get("bge-m3", {})
        if not isinstance(section, dict):
            raise ValueError("embeddings.providers.bge-m3 must be a mapping")
        allowed = {item.name for item in fields(cls)}
        unknown = set(section) - allowed
        if unknown:
            raise ValueError(f"Unknown BGE-M3 configuration fields: {', '.join(sorted(unknown))}")
        values = {**section, **{key: value for key, value in overrides.items() if value is not None}}
        cache_dir = values.get("cache_dir")
        if cache_dir and not Path(cache_dir).is_absolute():
            values["cache_dir"] = str((config.path.parent / cache_dir).resolve())
        return cls(**values)

    def with_overrides(self, **values: Any) -> "BGEM3Config":
        return replace(self, **{key: value for key, value in values.items() if value is not None})


def load_embedding_settings(config_path: str | Path | None = None) -> tuple[str, int]:
    config = load_services_config(config_path)
    section = config.data.get("embeddings", {})
    if not isinstance(section, dict):
        raise ValueError("embeddings must be a mapping")
    default = section.get("default_provider", "bge-m3")
    limit = section.get("max_texts_per_request", 256)
    if not isinstance(default, str) or not default:
        raise ValueError("embeddings.default_provider must be a non-empty string")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ValueError("embeddings.max_texts_per_request must be a positive integer")
    return default, limit

