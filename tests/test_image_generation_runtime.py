from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from aegis.capabilities import CapabilityInvocationRequest, CapabilityRuntime
from aegis.image_generation import ImageGenerationRuntime
from aegis.image_generation.models import ImageGenerationRequest
from aegis.image_generation.providers.comfyui import ComfyUIProvider
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

    result = runtime.generate(
        "a quiet workstation",
        output_dir=str(tmp_path / "images"),
        provider="stub",
    )

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

    result = runtime.generate(
        "project image",
        output_dir=str(tmp_path / "images"),
        seed=7,
        provider="stub",
    )

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
            payload={
                "prompt": "capability image",
                "output_dir": str(tmp_path / "images"),
                "provider": "stub",
            },
        )
    )

    assert result.success is True
    assert result.output["success"] is True
    assert Path(result.output["image_paths"][0]).exists()


def test_runtime_lists_stub_and_comfyui_providers(tmp_path):
    runtime = ImageGenerationRuntime(FakeCore(tmp_path))

    providers = {provider["name"]: provider for provider in runtime.providers()}

    assert "stub" in providers
    assert "comfyui" in providers
    assert providers["stub"]["available"] is True
    assert providers["comfyui"]["capabilities"]["mode"] == "comfyui"


def test_comfyui_provider_reports_missing_workflow(tmp_path):
    config_path = tmp_path / "comfyui.json"
    workflow_path = tmp_path / "missing.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "http://127.0.0.1:8188",
                "workflow_path": str(workflow_path),
                "output_dir": str(tmp_path / "images"),
                "timeout_seconds": 1,
            }
        ),
        encoding="utf-8",
    )
    provider = ComfyUIProvider(config_path=config_path)

    result = provider.generate(ImageGenerationRequest(prompt="test prompt"))

    assert result.success is False
    assert result.provider == "comfyui"
    assert result.error == "ComfyUI workflow not found"


def test_comfyui_provider_bypasses_http_environment_proxy_for_availability(tmp_path, monkeypatch):
    config_path = tmp_path / "comfyui.json"
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text("{}", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "base_url": "http://192.168.1.7:8188",
                "workflow_path": str(workflow_path),
                "output_dir": str(tmp_path / "images"),
            }
        ),
        encoding="utf-8",
    )
    fake_client = _FakeProxySensitiveClient()
    monkeypatch.setattr("aegis.image_generation.providers.comfyui.httpx.Client", fake_client.factory)

    provider = ComfyUIProvider(config_path=config_path)

    assert provider.available() is True
    assert fake_client.trust_env_values == [False]


def test_comfyui_doctor_reports_http_environment_503_without_failing_direct_lan(tmp_path, monkeypatch):
    config_path = tmp_path / "comfyui.json"
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text("{}", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "base_url": "http://192.168.1.7:8188",
                "workflow_path": str(workflow_path),
                "output_dir": str(tmp_path / "images"),
            }
        ),
        encoding="utf-8",
    )
    fake_client = _FakeProxySensitiveClient()
    monkeypatch.setattr("aegis.image_generation.providers.comfyui.httpx.Client", fake_client.factory)
    monkeypatch.setattr("aegis.image_generation.providers.comfyui.socket.create_connection", _fake_socket)

    report = ComfyUIProvider(config_path=config_path).doctor(verbose=True)

    environment_check = next(check for check in report.checks if check.name == "HTTP Environment")
    assert environment_check.status == "WARN"
    assert environment_check.status_code == 503
    assert report.proxy == "Caddy"
    assert report.overall_status == "READY"
    assert report.reason == ""


def test_comfyui_provider_executes_prompt_downloads_png_and_records_artifact(tmp_path, monkeypatch):
    config_path = tmp_path / "comfyui.json"
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
                "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
                "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
                "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
                "5": {
                    "class_type": "KSampler",
                    "inputs": {
                        "model": ["4", 0],
                        "positive": ["1", 0],
                        "negative": ["2", 0],
                        "latent_image": ["3", 0],
                        "seed": 0,
                        "steps": 20,
                    },
                },
                "6": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "ComfyUI"}},
            }
        ),
        encoding="utf-8",
    )
    workflow_path.with_name("default.meta.json").write_text(
        json.dumps({"model_family": "sd15", "category": "image", "task_type": "txt2img"}),
        encoding="utf-8",
    )
    config_path.write_text(
        json.dumps(
            {
                "base_url": "http://comfy.test",
                "workflow_path": str(workflow_path),
                "output_dir": str(tmp_path / "images"),
                "timeout_seconds": 2,
            }
        ),
        encoding="utf-8",
    )
    fake_client = _FakeComfyClient()
    monkeypatch.setattr("aegis.image_generation.providers.comfyui.httpx.Client", fake_client.factory)

    events = []
    provider = ComfyUIProvider(config_path=config_path, event_publisher=lambda event, payload: events.append(event))

    result = provider.generate(
        ImageGenerationRequest(
            prompt="test prompt",
            negative_prompt="blur",
            width=640,
            height=768,
            seed=123,
            workflow="workflow",
        )
    )

    assert result.success is True
    assert result.provider == "comfyui"
    assert result.workflow == "workflow"
    assert result.model_family == "sd15"
    assert result.seed == 123
    assert result.images == result.image_paths
    assert len(result.images) == 1
    output_path = Path(result.images[0])
    assert output_path.exists()
    assert output_path.name.startswith("202")
    assert output_path.name.endswith("-prompt-1-0.png")
    assert output_path.read_bytes().startswith(b"\x89PNG")
    assert result.artifacts[0]["provider"] == "comfyui"
    assert result.artifacts[0]["workflow"] == "workflow"
    assert result.artifacts[0]["model_family"] == "sd15"
    assert result.artifacts[0]["output_path"] == str(output_path)
    assert result.generation_time > 0
    assert "image.generation.progress" in events
    assert "image.artifact.saved" in events
    assert fake_client.submitted_prompt["1"]["inputs"]["text"] == "test prompt"
    assert fake_client.submitted_prompt["2"]["inputs"]["text"] == "blur"
    assert fake_client.submitted_prompt["3"]["inputs"]["width"] == 640
    assert fake_client.submitted_prompt["3"]["inputs"]["height"] == 768
    assert fake_client.submitted_prompt["5"]["inputs"]["seed"] == 123


class _FakeResponse:
    def __init__(self, data=None, content: bytes = b"", status_code: int = 200, headers=None):
        self._data = data
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.text = json.dumps(data or {}) if data is not None else content.decode(errors="ignore")

    def json(self):
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://comfy.test/history/prompt-1")
            raise httpx.HTTPStatusError("temporary error", request=request, response=self)


class _FakeComfyClient:
    def __init__(self):
        self.history_calls = 0
        self.submitted_prompt = {}

    def factory(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get(self, url):
        if url.endswith("/system_stats"):
            return _FakeResponse({"system": "ok"})
        if "/history/prompt-1" in url:
            self.history_calls += 1
            if self.history_calls == 1:
                return _FakeResponse(status_code=503)
            return _FakeResponse(
                {
                    "prompt-1": {
                        "status": {"status_str": "success"},
                        "outputs": {
                            "6": {
                                "images": [
                                    {
                                        "filename": "ComfyUI_00001_.png",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        },
                    }
                }
            )
        if "/view?" in url:
            image = Image.new("RGB", (4, 4), (12, 34, 56))
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return _FakeResponse(content=buffer.getvalue())
        raise AssertionError(f"Unexpected GET {url}")

    def post(self, url, json):
        assert url.endswith("/prompt")
        self.submitted_prompt = json["prompt"]
        return _FakeResponse({"prompt_id": "prompt-1"})


class _FakeProxySensitiveClient:
    def __init__(self):
        self.trust_env = False
        self.trust_env_values = []

    def factory(self, *args, **kwargs):
        self.trust_env = bool(kwargs.get("trust_env", True))
        self.trust_env_values.append(self.trust_env)
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get(self, url):
        if self.trust_env:
            return _FakeResponse(status_code=503)
        if url.endswith("/system_stats"):
            return _FakeResponse(
                {
                    "system": {
                        "comfyui_version": "v-test",
                        "argv": ["main.py", "--port", "18188"],
                    }
                },
                status_code=200,
                headers={"server": "Caddy, Python/3.10 aiohttp/3.10.6"},
            )
        if url.endswith("/object_info"):
            return _FakeResponse({}, status_code=200, headers={"server": "Caddy"})
        if url.endswith("/queue"):
            return _FakeResponse({"queue_running": [], "queue_pending": []}, status_code=200, headers={"server": "Caddy"})
        if url.endswith("/history"):
            return _FakeResponse({}, status_code=200, headers={"server": "Caddy"})
        if url.endswith("/view"):
            return _FakeResponse({}, status_code=404, headers={"server": "Caddy"})
        if url.endswith("/prompt"):
            return _FakeResponse({}, status_code=200, headers={"server": "Caddy"})
        raise AssertionError(f"Unexpected GET {url}")


class _FakeSocket:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def _fake_socket(*args, **kwargs):
    return _FakeSocket()
