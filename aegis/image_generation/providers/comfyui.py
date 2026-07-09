"""ComfyUI image generation provider."""

from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from PIL import Image

from aegis.image_generation.models import (
    ImageGenerationRequest,
    ImageGenerationResult,
)

CONFIG_PATH = Path(r"F:\AI_WORKSPACE\image_generation\comfyui.json")
DEFAULT_BASE_URL = "http://192.168.1.7:8188"
DEFAULT_WORKFLOW_PATH = Path(r"F:\AI_WORKSPACE\image_generation\workflows\default.json")
DEFAULT_OUTPUT_DIR = Path(r"F:\AI_WORKSPACE\images\generated")
DEFAULT_TIMEOUT_SECONDS = 300

EventPublisher = Callable[[str, dict[str, Any]], None]


class ComfyUIProvider:
    """Provider adapter for ComfyUI's HTTP API.

    The adapter treats the ComfyUI workflow as the model-specific boundary:
    AEGIS only patches common generation inputs and never hard-codes a model,
    checkpoint, sampler, or custom node.
    """

    name = "comfyui"

    def __init__(
        self,
        config_path: Path | str = CONFIG_PATH,
        event_publisher: EventPublisher | None = None,
    ):
        self.config_path = Path(config_path)
        self._event_publisher = event_publisher

    def available(self) -> bool:
        config = self._load_config()
        workflow_path = Path(config["workflow_path"])
        if not workflow_path.exists():
            return False
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{config['base_url'].rstrip('/')}/system_stats")
                return response.status_code < 500
        except httpx.HTTPError:
            return False

    def capabilities(self) -> dict:
        config = self._load_config()
        workflow_path = Path(config["workflow_path"])
        return {
            "mode": "comfyui",
            "requires_model": True,
            "formats": ["png"],
            "base_url": config["base_url"],
            "workflow_path": str(workflow_path),
            "workflow_exists": workflow_path.exists(),
            "default_output_dir": config["output_dir"],
            "timeout_seconds": config["timeout_seconds"],
        }

    def generate(
        self,
        request: ImageGenerationRequest,
    ) -> ImageGenerationResult:
        config = self._load_config()
        workflow_path = Path(config["workflow_path"])
        if not workflow_path.exists():
            result = self._failure(request, "ComfyUI workflow not found")
            self._publish("image.comfyui.failed", {"request": request, "result": result})
            return result

        try:
            workflow = self._load_workflow(workflow_path)
            patch_report = self._patch_workflow(workflow, request)
            prompt_id = self._submit_prompt(config, workflow)
            self._publish(
                "image.comfyui.prompt.submitted",
                {"prompt_id": prompt_id, "request": request, "patch_report": patch_report},
            )
            history = self._wait_for_history(config, prompt_id)
            image_paths = self._download_images(config, history, request)
            if not image_paths:
                raise RuntimeError("ComfyUI completed without image outputs")
            result = ImageGenerationResult(
                success=True,
                image_paths=image_paths,
                provider=self.name,
                prompt=request.prompt,
                seed=request.seed,
                metadata={
                    "prompt_id": prompt_id,
                    "workflow_path": str(workflow_path),
                    "base_url": config["base_url"],
                    "patch_report": patch_report,
                    "output_dir": self._output_dir(config, request),
                },
            )
            self._publish("image.comfyui.completed", {"request": request, "result": result})
            return result
        except Exception as exc:
            result = self._failure(request, str(exc))
            self._publish("image.comfyui.failed", {"request": request, "result": result})
            return result

    def _load_config(self) -> dict[str, Any]:
        config = {
            "base_url": DEFAULT_BASE_URL,
            "workflow_path": str(DEFAULT_WORKFLOW_PATH),
            "output_dir": str(DEFAULT_OUTPUT_DIR),
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        }
        if self.config_path.exists():
            data = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                config.update({key: value for key, value in data.items() if value not in (None, "")})
        config["base_url"] = str(config["base_url"]).rstrip("/")
        config["workflow_path"] = str(config["workflow_path"])
        config["output_dir"] = str(config["output_dir"])
        config["timeout_seconds"] = int(config["timeout_seconds"] or DEFAULT_TIMEOUT_SECONDS)
        return config

    def _load_workflow(self, workflow_path: Path) -> dict[str, Any]:
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("ComfyUI workflow must be a JSON object")
        return data

    def _patch_workflow(
        self,
        workflow: dict[str, Any],
        request: ImageGenerationRequest,
    ) -> dict[str, int]:
        report = {
            "prompt_nodes": 0,
            "negative_prompt_nodes": 0,
            "seed_nodes": 0,
            "steps_nodes": 0,
            "size_nodes": 0,
        }
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            class_type = str(node.get("class_type", ""))
            title = str(node.get("_meta", {}).get("title", ""))
            label = f"{node_id} {class_type} {title}".lower()

            if "text" in inputs and self._is_prompt_node(class_type, inputs):
                if self._is_negative_node(label):
                    if request.negative_prompt:
                        inputs["text"] = request.negative_prompt
                        report["negative_prompt_nodes"] += 1
                else:
                    inputs["text"] = request.prompt
                    report["prompt_nodes"] += 1

            if request.seed is not None and "seed" in inputs:
                inputs["seed"] = int(request.seed)
                report["seed_nodes"] += 1
            if "steps" in inputs:
                inputs["steps"] = int(request.steps)
                report["steps_nodes"] += 1
            if "width" in inputs:
                inputs["width"] = int(request.width)
                report["size_nodes"] += 1
            if "height" in inputs:
                inputs["height"] = int(request.height)

        if report["prompt_nodes"] == 0:
            raise ValueError("ComfyUI workflow has no prompt text input")
        return report

    def _is_prompt_node(self, class_type: str, inputs: dict[str, Any]) -> bool:
        if class_type == "CLIPTextEncode":
            return True
        return isinstance(inputs.get("text"), str)

    def _is_negative_node(self, label: str) -> bool:
        return any(token in label for token in ("negative", "neg", "uncond"))

    def _submit_prompt(self, config: dict[str, Any], workflow: dict[str, Any]) -> str:
        timeout = float(config["timeout_seconds"])
        payload = {"prompt": workflow, "client_id": f"aegis-{uuid4().hex}"}
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{config['base_url']}/prompt", json=payload)
            response.raise_for_status()
            data = response.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return prompt_id")
        return str(prompt_id)

    def _wait_for_history(self, config: dict[str, Any], prompt_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + float(config["timeout_seconds"])
        with httpx.Client(timeout=10.0) as client:
            while time.monotonic() < deadline:
                response = client.get(f"{config['base_url']}/history/{prompt_id}")
                response.raise_for_status()
                data = response.json()
                history = data.get(prompt_id) if isinstance(data, dict) else None
                if isinstance(history, dict):
                    status = history.get("status", {})
                    if isinstance(status, dict) and status.get("status_str") == "error":
                        messages = status.get("messages") or []
                        raise RuntimeError(f"ComfyUI generation failed: {messages}")
                    outputs = history.get("outputs")
                    if isinstance(outputs, dict) and outputs:
                        return history
                time.sleep(1.0)
        raise TimeoutError("ComfyUI generation timed out")

    def _download_images(
        self,
        config: dict[str, Any],
        history: dict[str, Any],
        request: ImageGenerationRequest,
    ) -> list[str]:
        output_dir = Path(self._output_dir(config, request))
        output_dir.mkdir(parents=True, exist_ok=True)
        image_paths: list[str] = []
        outputs = history.get("outputs", {})
        with httpx.Client(timeout=float(config["timeout_seconds"])) as client:
            for node_output in outputs.values():
                if not isinstance(node_output, dict):
                    continue
                for image in node_output.get("images", []):
                    if not isinstance(image, dict):
                        continue
                    params = {
                        "filename": image.get("filename", ""),
                        "subfolder": image.get("subfolder", ""),
                        "type": image.get("type", "output"),
                    }
                    response = client.get(f"{config['base_url']}/view?{urlencode(params)}")
                    response.raise_for_status()
                    path = output_dir / f"comfyui_{uuid4().hex}.png"
                    with Image.open(BytesIO(response.content)) as generated_image:
                        generated_image.save(path, format="PNG")
                    image_paths.append(str(path))
        return image_paths

    def _output_dir(self, config: dict[str, Any], request: ImageGenerationRequest) -> str:
        return request.output_dir or str(config["output_dir"])

    def _failure(self, request: ImageGenerationRequest, error: str) -> ImageGenerationResult:
        return ImageGenerationResult(
            success=False,
            provider=self.name,
            prompt=request.prompt,
            seed=request.seed,
            error=error,
        )

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_publisher is None:
            return
        self._event_publisher(event_type, payload)
