"""Image Generation Runtime v1."""

from __future__ import annotations

from typing import Any

from aegis.capabilities import CapabilityDescriptor
from aegis.serialization import to_plain

from .models import ImageGenerationRequest, ImageGenerationResult
from .providers.stub import StubImageGenerationProvider


class ImageGenerationRuntime:
    """Provider-neutral facade for raster image generation."""

    def __init__(self, core: Any):
        self.core = core
        self._providers = {"stub": StubImageGenerationProvider()}
        self._default_provider = "stub"

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
        metadata: dict[str, Any] | None = None,
    ) -> ImageGenerationResult:
        payload = prompt if isinstance(prompt, dict) else {}
        request = ImageGenerationRequest(
            prompt=str(payload.get("prompt") if isinstance(prompt, dict) else prompt),
            negative_prompt=str(payload.get("negative_prompt", negative_prompt)),
            width=int(payload.get("width", width) or width),
            height=int(payload.get("height", height) or height),
            steps=int(payload.get("steps", steps) or steps),
            seed=self._optional_int(payload.get("seed", seed)),
            style=str(payload.get("style", style)),
            output_dir=str(payload.get("output_dir", output_dir)),
            metadata=dict(payload.get("metadata") or metadata or {}),
        )
        provider_name = str(payload.get("provider") or provider or self._default_provider)
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
                raise RuntimeError(f"Image generation provider unavailable: {provider_name}")
            result = image_provider.generate(request)
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
            artifact = add_artifact(
                active_project.id,
                "image.generated",
                path,
                metadata={
                    "provider": result.provider,
                    "prompt": request.prompt,
                    "negative_prompt": request.negative_prompt,
                    "seed": result.seed,
                    "style": request.style,
                    "width": request.width,
                    "height": request.height,
                    "steps": request.steps,
                },
            )
            artifacts.append(to_plain(artifact))
        return artifacts

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
