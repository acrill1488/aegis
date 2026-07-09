from __future__ import annotations

from pathlib import Path

from aegis.capabilities import CapabilityInvocationRequest, CapabilityRuntime
from aegis.image_generation import ImageGenerationRuntime
from aegis.project_runtime import ProjectRegistry, ProjectRuntime


class FakeEvents:
    def __init__(self):
        self.published = []

    def publish(self, event_type, source, payload=None, **context):
        self.published.append((event_type, source, payload, context))


class FakeCore:
    def __init__(self, tmp_path: Path):
        self.events = FakeEvents()
        self.project_runtime = ProjectRuntime(
            self,
            registry=ProjectRegistry(tmp_path / "projects"),
            legacy_mission_root=tmp_path / "missions",
        )
        self.registry = _Registry()
        self.capability_runtime = CapabilityRuntime(self)
        self.image_generation = ImageGenerationRuntime(self)
        self.registry.register("image_generation", self.image_generation)


class _Registry:
    def __init__(self):
        self.services = {}

    def register(self, name, service):
        self.services[name] = service

    def get(self, name):
        return self.services.get(name)


def test_stub_provider_generates_placeholder_png_and_events(tmp_path):
    runtime = ImageGenerationRuntime(FakeCore(tmp_path))

    result = runtime.generate("a quiet workstation", output_dir=str(tmp_path / "images"))

    assert result.success is True
    assert result.provider == "stub"
    assert len(result.image_paths) == 1
    assert Path(result.image_paths[0]).suffix == ".png"
    assert Path(result.image_paths[0]).read_bytes().startswith(b"\x89PNG")
    assert [event[0] for event in runtime.core.events.published] == [
        "image.generation.started",
        "image.generation.completed",
    ]


def test_generation_registers_active_project_artifact(tmp_path):
    core = FakeCore(tmp_path)
    project = core.project_runtime.create("Image project")
    core.project_runtime.set_active(project.id)
    runtime = core.image_generation

    result = runtime.generate("project image", output_dir=str(tmp_path / "images"), seed=7)

    artifacts = core.project_runtime.artifacts(project.id)
    assert result.success is True
    assert artifacts[0].type == "image.generated"
    assert artifacts[0].path == result.image_paths[0]
    assert artifacts[0].metadata["prompt"] == "project image"
    assert artifacts[0].metadata["seed"] == 7
    assert result.metadata["project_artifacts"][0]["type"] == "image.generated"


def test_image_generation_registers_capabilities_and_invokes_runtime(tmp_path):
    core = FakeCore(tmp_path)
    core.image_generation.register_capabilities()

    descriptors = {descriptor.id: descriptor for descriptor in core.capability_runtime.list()}
    assert "image.generate" in descriptors
    assert "image.providers" in descriptors

    result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="image.generate",
            payload={"prompt": "capability image", "output_dir": str(tmp_path / "images")},
        )
    )

    assert result.success is True
    assert result.output["success"] is True
    assert Path(result.output["image_paths"][0]).exists()
