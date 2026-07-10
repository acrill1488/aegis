"""Image Generation Runtime v1."""

from __future__ import annotations

from typing import Any

from aegis.capabilities import CapabilityDescriptor
from aegis.serialization import to_plain
from aegis.workflow_library import WorkflowLibraryRuntime

from .models import ImageGenerationRequest, ImageGenerationResult
from .providers.comfyui import ComfyUIProvider
from .providers.stub import StubImageGenerationProvider


class ImageGenerationRuntime:
    """Provider-neutral facade for raster image generation."""

    def __init__(self, core: Any):
        self.core = core
        self._providers = {
            "stub": StubImageGenerationProvider(),
            "comfyui": ComfyUIProvider(event_publisher=self._publish),
        }
        self.workflow_library = WorkflowLibraryRuntime(core)
        self._default_provider = self._select_default_provider()

    def generate(
        self,
        prompt: str | dict,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        seed: int | None = None,
        style: str = "",
        output_dir: str = "",
        provider: str | None = None,
        workflow: str | None = None,
        model_family: str | None = None,
        task_type: str = "txt2img",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ImageGenerationResult:
        payload = prompt if isinstance(prompt, dict) else {}
        request_metadata = dict(payload.get("metadata") or metadata or {})
        request = ImageGenerationRequest(
            prompt=str(payload.get("prompt") if isinstance(prompt, dict) else prompt),
            negative_prompt=str(payload.get("negative_prompt", negative_prompt)),
            width=int(payload.get("width", width) or width),
            height=int(payload.get("height", height) or height),
            steps=int(payload.get("steps", steps) or steps),
            seed=self._optional_int(payload.get("seed", seed)),
            style=str(payload.get("style", style)),
            output_dir=str(payload.get("output_dir", output_dir)),
            workflow=str(payload.get("workflow") or workflow or ""),
            model_family=str(payload.get("model_family") or model_family or ""),
            task_type=str(payload.get("task_type") or task_type or "txt2img"),
            tags=[str(tag) for tag in payload.get("tags", tags or [])],
            metadata=request_metadata,
        )
        provider_name = str(payload.get("provider") or provider or self._default_provider)
        if provider_name == "comfyui":
            workflow_result = self._resolve_workflow(request)
            if workflow_result is not None:
                return workflow_result
        image_provider = self._providers.get(provider_name)
        if image_provider is None:
            result = ImageGenerationResult(
                success=False,
                provider=provider_name,
                prompt=request.prompt,
                seed=request.seed,
                error=f"Image generation provider not found: {provider_name}",
            )
            self._publish("image.generation.failed", {"request": request, "result": result})
            return result

        self._publish(
            "image.generation.started",
            {"provider": provider_name, "request": request},
        )
        try:
            if not image_provider.available():
                self._publish(
                    "image.provider.unavailable",
                    {"provider": provider_name, "request": request},
                )
            result = image_provider.generate(request)
            result.workflow = result.workflow or request.workflow
            result.model_family = result.model_family or request.model_family
            if not result.images:
                result.images = list(result.image_paths)
            result.metadata = {
                **result.metadata,
                "project_artifacts": self._register_project_artifacts(result, request),
            }
        except Exception as exc:
            result = ImageGenerationResult(
                success=False,
                provider=provider_name,
                prompt=request.prompt,
                seed=request.seed,
                error=str(exc),
            )

        event_type = "image.generation.completed" if result.success else "image.generation.failed"
        self._publish(event_type, {"request": request, "result": result})
        return result

    def models(self, payload: dict | None = None) -> list[dict[str, Any]]:
        from .model_catalog import ImageModelCatalog

        return [to_plain(model) for model in ImageModelCatalog(core=self.core).list()]

    def providers(self, payload: dict | None = None) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "available": provider.available(),
                "default": name == self._default_provider,
                "capabilities": provider.capabilities(),
            }
            for name, provider in sorted(self._providers.items())
        ]

    def default_provider(self) -> str:
        return self._default_provider

    def _select_default_provider(self) -> str:
        comfyui = self._providers.get("comfyui")
        if comfyui is not None and comfyui.available():
            return "comfyui"
        configured = getattr(comfyui, "configured", None)
        if comfyui is not None and callable(configured) and configured():
            return "comfyui"
        return "stub"

    def register_capabilities(self) -> None:
        capability_runtime = getattr(self.core, "capability_runtime", None)
        if capability_runtime is None:
            return
        specs = (
            ("image.generate", "Generate Image", "generate", ["image.generate"]),
            ("image.providers", "List Image Providers", "providers", ["image.providers"]),
        )
        for capability_id, name, method, permissions in specs:
            descriptor = CapabilityDescriptor(
                id=capability_id,
                name=name,
                version="1",
                owner_agent="image_generation",
                machine_scope="local",
                permissions=permissions,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                tags=["image", "generation", "runtime"],
                metadata={
                    "provider_type": "runtime",
                    "description": name,
                },
            )
            capability_runtime.unregister(descriptor.id)
            capability_runtime.register(
                descriptor,
                {"type": "runtime", "runtime": "image_generation", "method": method},
            )

    def _register_project_artifacts(
        self,
        result: ImageGenerationResult,
        request: ImageGenerationRequest,
    ) -> list[dict[str, Any]]:
        if not result.success:
            return []
        project_runtime = getattr(self.core, "project_runtime", None)
        get_active = getattr(project_runtime, "get_active", None)
        add_artifact = getattr(project_runtime, "add_artifact", None)
        if not callable(get_active) or not callable(add_artifact):
            return []
        active_project = get_active()
        if active_project is None:
            return []

        artifacts = []
        for path in result.image_paths:
            metadata = {
                "provider": result.provider,
                "workflow": result.workflow or request.workflow,
                "model_family": result.model_family or request.model_family,
                "seed": result.seed,
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "width": request.width,
                "height": request.height,
                "generation_time": result.generation_time,
                "output_path": path,
                "style": request.style,
                "steps": request.steps,
            }
            artifact = add_artifact(
                active_project.id,
                "image.generated",
                path,
                metadata=metadata,
            )
            plain_artifact = to_plain(artifact)
            artifacts.append(plain_artifact)
            self._publish("image.artifact.saved", {"artifact": plain_artifact, "request": request})
        result.artifacts.extend(
            item for item in artifacts if item not in result.artifacts
        )
        return artifacts

    def _resolve_workflow(self, request: ImageGenerationRequest) -> ImageGenerationResult | None:
        template = None
        if request.workflow:
            template = self.workflow_library.get(request.workflow)
            if template is None:
                result = ImageGenerationResult(
                    success=False,
                    provider="comfyui",
                    prompt=request.prompt,
                    seed=request.seed,
                    error=f"ComfyUI workflow not found in catalog: {request.workflow}",
                )
                self._publish("image.generation.failed", {"request": request, "result": result})
                return result
        else:
            template = self.workflow_library.select(
                request.task_type,
                model_family=request.model_family or None,
                tags=request.tags or None,
            )
            if template is None:
                result = ImageGenerationResult(
                    success=False,
                    provider="comfyui",
                    prompt=request.prompt,
                    seed=request.seed,
                    error=(
                        "ComfyUI workflow is required. Run 'aegis workflow scan' and pass "
                        "--workflow WORKFLOW_ID, or add a matching workflow to the catalog."
                    ),
                )
                self._publish("image.generation.failed", {"request": request, "result": result})
                return result
        validation = self.workflow_library.validate(template.id)
        request.workflow = template.id
        request.model_family = request.model_family or template.model_family
        request.width = request.width or template.default_width
        request.height = request.height or template.default_height
        request.metadata = {
            **request.metadata,
            "workflow_id": template.id,
            "workflow_path": template.path,
            "workflow_validation": to_plain(validation),
        }
        return None

    def _optional_int(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        events = getattr(self.core, "events", None)
        publish = getattr(events, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, source="image_generation_runtime", payload=to_plain(payload))
        except Exception:
            return
