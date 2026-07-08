from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import ModelRecord


DEFAULT_MODEL_REGISTRY_PATH = Path(r"F:\AI_WORKSPACE\models\registry.json")


class ModelRegistry:
    """Persistent catalog of model capabilities known to AEGIS."""

    def __init__(self, path: str | Path = DEFAULT_MODEL_REGISTRY_PATH):
        self.path = Path(path)
        self._models: dict[str, ModelRecord] = {}
        self._persistence_available = True
        self._ensure_file()
        self._load()

    def add(self, record: ModelRecord) -> ModelRecord:
        self._models[record.id] = record
        self._save()
        return record

    def get(self, model_id: str) -> ModelRecord | None:
        return self._models.get(model_id)

    def list(
        self,
        task_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[ModelRecord]:
        records = list(self._models.values())
        if task_type is not None:
            records = [
                record for record in records if task_type in record.task_types
            ]
        if enabled_only:
            records = [record for record in records if record.enabled]
        return records

    def enable(self, model_id: str) -> ModelRecord:
        record = self._require_model(model_id)
        record.enabled = True
        self._save()
        return record

    def disable(self, model_id: str) -> ModelRecord:
        record = self._require_model(model_id)
        record.enabled = False
        self._save()
        return record

    def remove(self, model_id: str) -> bool:
        if model_id not in self._models:
            return False
        del self._models[model_id]
        self._save()
        return True

    def seed_defaults(self) -> int:
        added = 0
        for record in _default_models():
            if record.id in self._models:
                continue
            self._models[record.id] = record
            added += 1
        if added:
            self._save()
        return added

    def _require_model(self, model_id: str) -> ModelRecord:
        record = self.get(model_id)
        if record is None:
            raise KeyError(f"Model not found: {model_id}")
        return record

    def _ensure_file(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.write_text("[]", encoding="utf-8")
        except OSError:
            self._persistence_available = False

    def _load(self) -> None:
        if not self._persistence_available:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []

        if isinstance(data, dict):
            items = data.get("models", data.values())
        elif isinstance(data, list):
            items = data
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                record = self._record_from_plain(item)
            except (KeyError, TypeError, ValueError):
                continue
            self._models[record.id] = record

        self._save()

    def _save(self) -> None:
        if not self._persistence_available:
            return
        try:
            self.path.write_text(
                json.dumps(
                    to_plain(self.list()),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            self._persistence_available = False

    def _record_from_plain(self, item: dict[str, Any]) -> ModelRecord:
        task_types = self._string_list(item.get("task_types"))
        input_modalities = self._string_list(item.get("input_modalities"))
        output_modalities = self._string_list(item.get("output_modalities"))
        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        return ModelRecord(
            id=str(item["id"]),
            name=str(item["name"]),
            provider=str(item["provider"]),
            model_ref=str(item["model_ref"]),
            task_types=task_types,
            context_window=self._optional_int(item.get("context_window")),
            input_modalities=input_modalities,
            output_modalities=output_modalities,
            quantization=self._optional_str(item.get("quantization")),
            ram_required_gb=self._optional_float(item.get("ram_required_gb")),
            vram_required_gb=self._optional_float(item.get("vram_required_gb")),
            quality_tier=str(item.get("quality_tier", "unknown")),
            speed_tier=str(item.get("speed_tier", "unknown")),
            license=self._optional_str(item.get("license")),
            enabled=bool(item.get("enabled", True)),
            metadata=metadata,
        )

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _optional_str(self, value: Any) -> str | None:
        return str(value) if value is not None else None

    def _optional_int(self, value: Any) -> int | None:
        return int(value) if value is not None else None

    def _optional_float(self, value: Any) -> float | None:
        return float(value) if value is not None else None


def _default_models() -> list[ModelRecord]:
    return [
        ModelRecord(
            id="qwen3-local",
            name="Qwen3 Local",
            provider="local",
            model_ref="qwen3",
            task_types=["general", "research", "planning"],
            input_modalities=["text"],
            output_modalities=["text"],
            quality_tier="balanced",
            speed_tier="balanced",
        ),
        ModelRecord(
            id="qwen3-coder",
            name="Qwen3 Coder",
            provider="local",
            model_ref="qwen3-coder",
            task_types=["coding"],
            input_modalities=["text"],
            output_modalities=["text"],
            quality_tier="high",
            speed_tier="balanced",
        ),
        ModelRecord(
            id="qwopus-coder",
            name="Qwopus Coder",
            provider="local",
            model_ref="Jackrong/Qwopus3.6-35B-A3B-Coder-MTP-GGUF",
            task_types=["coding"],
            input_modalities=["text"],
            output_modalities=["text"],
            quality_tier="high",
            speed_tier="balanced",
        ),
        ModelRecord(
            id="whisper-large-v3",
            name="Whisper Large v3",
            provider="transformers",
            model_ref="openai/whisper-large-v3",
            task_types=["speech.asr"],
            input_modalities=["audio"],
            output_modalities=["text"],
            quality_tier="high",
            speed_tier="balanced",
        ),
        ModelRecord(
            id="supra-router",
            name="Supra Router",
            provider="transformers",
            model_ref="SupraLabs/Supra-Router-51M",
            task_types=["router"],
            input_modalities=["text"],
            output_modalities=["labels"],
            quality_tier="balanced",
            speed_tier="fast",
        ),
        ModelRecord(
            id="qwen-vl",
            name="Qwen VL",
            provider="local",
            model_ref="qwen-vl",
            task_types=["vision"],
            input_modalities=["text", "image"],
            output_modalities=["text"],
            quality_tier="balanced",
            speed_tier="balanced",
        ),
        ModelRecord(
            id="qwen-embedding",
            name="Qwen Embedding",
            provider="local",
            model_ref="qwen-embedding",
            task_types=["embeddings"],
            input_modalities=["text"],
            output_modalities=["embeddings"],
            quality_tier="balanced",
            speed_tier="fast",
        ),
        ModelRecord(
            id="qwen-reranker",
            name="Qwen Reranker",
            provider="local",
            model_ref="qwen-reranker",
            task_types=["reranking"],
            input_modalities=["text"],
            output_modalities=["scores"],
            quality_tier="balanced",
            speed_tier="fast",
        ),
        ModelRecord(
            id="cosyvoice",
            name="CosyVoice",
            provider="local",
            model_ref="cosyvoice",
            task_types=["speech.tts"],
            input_modalities=["text"],
            output_modalities=["audio"],
            quality_tier="balanced",
            speed_tier="balanced",
        ),
        ModelRecord(
            id="fish-speech",
            name="Fish Speech",
            provider="local",
            model_ref="fish-speech",
            task_types=["speech.tts"],
            input_modalities=["text"],
            output_modalities=["audio"],
            quality_tier="balanced",
            speed_tier="balanced",
        ),
    ]
