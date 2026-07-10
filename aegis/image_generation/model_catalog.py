"""Image model catalog for local and ComfyUI-backed generation."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

IMAGE_GENERATION_ROOT = Path(r"F:\AI_WORKSPACE\image_generation")
MODEL_CATALOG_PATH = IMAGE_GENERATION_ROOT / "models" / "catalog.json"
LOCAL_MODELS_ROOT = IMAGE_GENERATION_ROOT / "models"
COMFYUI_NETWORK_MODELS_ROOT = Path(r"\\192.168.1.7\aegis\comfyui\models")
MODEL_SUBDIRS = {
    "checkpoint": "checkpoints",
    "lora": "loras",
    "vae": "vae",
    "controlnet": "controlnet",
}
MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}


@dataclass
class ImageModel:
    id: str
    name: str
    type: str
    family: str
    source_url: str = ""
    filename: str = ""
    local_path: str = ""
    installed: bool = False
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ImageModelCatalog:
    """JSON-backed catalog of image generation models."""

    def __init__(
        self,
        catalog_path: Path | str = MODEL_CATALOG_PATH,
        *,
        core: Any | None = None,
    ):
        self.catalog_path = Path(catalog_path)
        self.core = core
        self.ensure_layout()
        self._seed_defaults()

    def ensure_layout(self) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_MODELS_ROOT.mkdir(parents=True, exist_ok=True)
        if not self.catalog_path.exists():
            self._save([])

    def list(self) -> list[ImageModel]:
        data = json.loads(self.catalog_path.read_text(encoding="utf-8-sig") or "[]")
        items = data.get("models", []) if isinstance(data, dict) else data
        return [self._model_from_dict(item) for item in items if isinstance(item, dict)]

    def get(self, id: str) -> ImageModel | None:
        return next((model for model in self.list() if model.id == id), None)

    def register(self, model: ImageModel) -> ImageModel:
        models = {item.id: item for item in self.list()}
        models[model.id] = model
        self._save(list(models.values()))
        self._publish("image.model.registered", {"model": model})
        return model

    def mark_installed(self, id: str, local_path: str | Path) -> ImageModel:
        model = self.get(id)
        if model is None:
            raise KeyError(f"Image model not found: {id}")
        model.local_path = str(local_path)
        model.filename = model.filename or Path(local_path).name
        model.installed = True
        return self.register(model)

    def detect_installed(self, comfyui_models_root: str | Path | None = None) -> list[ImageModel]:
        root = Path(comfyui_models_root) if comfyui_models_root else self.default_comfyui_models_root()
        detected_files = self._detect_model_files(root)
        models = {model.id: model for model in self.list()}
        detected: list[ImageModel] = []
        for model_path, model_type in detected_files:
            match = self._match_known_model(model_path, models.values())
            if match is None:
                match = ImageModel(
                    id=self._slug(model_path.stem),
                    name=model_path.stem.replace("_", " ").replace("-", " ").title(),
                    type=model_type,
                    family="",
                    filename=model_path.name,
                    local_path=str(model_path),
                    installed=True,
                    metadata={"detected": True},
                )
            else:
                match.type = match.type or model_type
                match.filename = model_path.name
                match.local_path = str(model_path)
                match.installed = True
            models[match.id] = match
            detected.append(match)
            self._publish("image.model.detected", {"model": match, "root": str(root)})
        self._save(list(models.values()))
        return sorted(detected, key=lambda item: item.id)

    def search(self, query: str) -> list[ImageModel]:
        needle = query.lower()
        return [model for model in self.list() if needle in self._search_text(model)]

    def default_comfyui_models_root(self) -> Path:
        try:
            if COMFYUI_NETWORK_MODELS_ROOT.exists():
                return COMFYUI_NETWORK_MODELS_ROOT
        except OSError:
            pass
        return LOCAL_MODELS_ROOT

    def _detect_model_files(self, root: Path) -> list[tuple[Path, str]]:
        if not root.exists():
            return []
        detected: list[tuple[Path, str]] = []
        for model_type, subdir in MODEL_SUBDIRS.items():
            path = root / subdir
            if not path.exists():
                continue
            try:
                files = [
                    item
                    for item in path.rglob("*")
                    if item.is_file() and item.suffix.lower() in MODEL_EXTENSIONS
                ]
            except OSError:
                continue
            detected.extend((item, model_type) for item in files)
        return detected

    def _match_known_model(
        self,
        model_path: Path,
        models: list[ImageModel] | Any,
    ) -> ImageModel | None:
        normalized_name = self._slug(model_path.stem)
        compact_name = normalized_name.replace("-", "")
        for model in models:
            filename = model.filename.lower() if model.filename else ""
            if filename and filename == model_path.name.lower():
                return model
            model_slug = self._slug(model.name)
            compact_model_id = model.id.replace("-", "")
            compact_model_slug = model_slug.replace("-", "")
            if (
                model.id in normalized_name
                or model_slug in normalized_name
                or compact_model_id in compact_name
                or compact_model_slug in compact_name
            ):
                return model
        return None

    def _seed_defaults(self) -> None:
        models = {model.id: model for model in self.list()}
        defaults = [
            ImageModel(
                id="anylora-checkpoint",
                name="AnyLoRA Checkpoint",
                type="checkpoint",
                family="sd15",
                source_url="https://civitai.com/models/23900/anylora-checkpoint",
                tags=["anime", "stylized", "lora-friendly", "character"],
                metadata={"roadmap": True},
            ),
            ImageModel(
                id="dreamshaper-xl",
                name="DreamShaper XL",
                type="checkpoint",
                family="sdxl",
                source_url="https://civitai.com/models/112902/dreamshaper-xl",
                tags=["universal", "concept-art", "tattoo", "stylized", "semi-real"],
                metadata={"roadmap": True},
            ),
        ]
        changed = False
        for model in defaults:
            if model.id not in models:
                models[model.id] = model
                changed = True
        if changed:
            self._save(list(models.values()))

    def _save(self, models: list[ImageModel]) -> None:
        payload = {
            "version": 1,
            "models": [asdict(model) for model in sorted(models, key=lambda item: item.id)],
        }
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _model_from_dict(self, data: dict[str, Any]) -> ImageModel:
        return ImageModel(
            id=str(data.get("id", "")),
            name=str(data.get("name") or data.get("id") or "Unnamed model"),
            type=str(data.get("type", "")),
            family=str(data.get("family", "")),
            source_url=str(data.get("source_url", "")),
            filename=str(data.get("filename", "")),
            local_path=str(data.get("local_path", "")),
            installed=bool(data.get("installed", False)),
            tags=[str(item) for item in data.get("tags", [])],
            metadata=dict(data.get("metadata") or {}),
        )

    def _search_text(self, model: ImageModel) -> str:
        return " ".join(
            [
                model.id,
                model.name,
                model.type,
                model.family,
                model.source_url,
                model.filename,
                " ".join(model.tags),
                json.dumps(model.metadata, ensure_ascii=False),
            ]
        ).lower()

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "model"

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        events = getattr(self.core, "events", None)
        publish = getattr(events, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, source="image_model_catalog", payload=to_plain(payload))
        except Exception:
            return
