from __future__ import annotations

import json
from pathlib import Path

from aegis.image_generation import ImageGenerationRuntime
from aegis.image_generation.model_catalog import ImageModelCatalog
from aegis.workflow_library import WorkflowLibraryRuntime, WorkflowLibraryStore, WorkflowTemplate


class FakeEvents:
    def __init__(self):
        self.published = []

    def publish(self, event_type, source, payload=None, **context):
        self.published.append((event_type, source, payload, context))


class FakeCore:
    def __init__(self):
        self.events = FakeEvents()


def test_image_model_catalog_seeds_defaults_and_searches(tmp_path):
    catalog = ImageModelCatalog(tmp_path / "models" / "catalog.json")

    models = {model.id: model for model in catalog.list()}

    assert models["anylora-checkpoint"].family == "sd15"
    assert models["dreamshaper-xl"].family == "sdxl"
    assert catalog.search("tattoo")[0].id == "dreamshaper-xl"


def test_image_model_catalog_detects_comfyui_models_without_network_root(tmp_path):
    root = tmp_path / "comfyui" / "models"
    checkpoint = root / "checkpoints" / "DreamShaperXL_v21.safetensors"
    lora = root / "loras" / "detail_lora.safetensors"
    checkpoint.parent.mkdir(parents=True)
    lora.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"checkpoint")
    lora.write_bytes(b"lora")
    catalog = ImageModelCatalog(tmp_path / "catalog.json")

    detected = catalog.detect_installed(root)

    assert {model.type for model in detected} == {"checkpoint", "lora"}
    assert catalog.get("dreamshaper-xl").installed is True


def test_workflow_library_scans_meta_and_selects_by_family_and_tag(tmp_path):
    workflow_path = tmp_path / "tattoo.json"
    workflow_path.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}}}))
    workflow_path.with_name("tattoo.meta.json").write_text(
        json.dumps(
            {
                "id": "tattoo-sdxl",
                "name": "Tattoo SDXL",
                "category": "image",
                "task_type": "txt2img",
                "model_family": "sdxl",
                "required_models": ["dreamshaper-xl"],
                "default_width": 1024,
                "default_height": 1024,
                "tags": ["tattoo", "stylized"],
            }
        ),
        encoding="utf-8",
    )
    model_catalog = ImageModelCatalog(tmp_path / "models" / "catalog.json")
    model_catalog.mark_installed("dreamshaper-xl", tmp_path / "DreamShaperXL_v21.safetensors")
    runtime = WorkflowLibraryRuntime(
        FakeCore(),
        store=WorkflowLibraryStore(tmp_path / "workflows" / "catalog.json"),
        model_catalog=model_catalog,
    )

    scanned = runtime.scan(tmp_path)
    selected = runtime.select("txt2img", model_family="sdxl", tags=["tattoo"])
    validation = runtime.validate("tattoo-sdxl")

    assert scanned[0].id == "tattoo-sdxl"
    assert selected is not None
    assert selected.id == "tattoo-sdxl"
    assert validation.success is True


def test_comfyui_generation_requires_catalog_workflow_when_not_available(tmp_path):
    core = FakeCore()
    runtime = ImageGenerationRuntime(core)
    runtime.workflow_library = WorkflowLibraryRuntime(
        core,
        store=WorkflowLibraryStore(tmp_path / "workflows" / "catalog.json"),
        model_catalog=ImageModelCatalog(tmp_path / "models" / "catalog.json"),
    )

    result = runtime.generate("test", provider="comfyui", model_family="sd15")

    assert result.success is False
    assert "workflow is required" in result.error


def test_comfyui_generation_uses_explicit_catalog_workflow(tmp_path):
    core = FakeCore()
    workflow_path = tmp_path / "simple.json"
    workflow_path.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}}}))
    workflow_store = WorkflowLibraryStore(tmp_path / "workflows" / "catalog.json")
    workflow_runtime = WorkflowLibraryRuntime(
        core,
        store=workflow_store,
        model_catalog=ImageModelCatalog(tmp_path / "models" / "catalog.json"),
    )
    workflow_runtime.register(
        WorkflowTemplate(
            id="simple",
            name="Simple",
            path=str(workflow_path),
            task_type="txt2img",
            model_family="sd15",
        )
    )
    runtime = ImageGenerationRuntime(core)
    runtime.workflow_library = workflow_runtime

    result = runtime.generate("test", provider="comfyui", workflow="simple")

    assert result.success is False
    assert result.error != "ComfyUI workflow not found"
