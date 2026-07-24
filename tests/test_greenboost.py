from __future__ import annotations

import json
import subprocess

from PIL import Image

from aegis.greenboost import GreenBoostRuntime


def _config(tmp_path):
    path = tmp_path / "greenboost.yaml"
    path.write_text(
        """
enabled: true
default_profile: ocr_rtx3050
upstream: {url: https://gitlab.example/greenboost.git, commit: abc123}
gpu_snapshot_command: snapshot
poll_interval_seconds: 0
vram_wait_timeout_seconds: 1
profiles:
  ocr_rtx3050:
    required_free_vram_mb: 7000
    gpu_memory_limit_gb: 5.5
    max_image_side: 1024
    cpu_offload: true
    stoppable_services: [comfyui]
    unloadable_ollama_models: []
    restore_stopped_services: true
    retry_policy:
      - {name: normal, max_image_side: 1024}
      - {name: memory_saver, max_image_side: 768}
      - {name: emergency, max_image_side: 640}
services: {}
""",
        encoding="utf-8",
    )
    return path


def test_plan_is_bounded_and_pinned(tmp_path):
    runtime = GreenBoostRuntime(_config(tmp_path), command_runner=lambda c, t: subprocess.CompletedProcess(c, 0, json.dumps({"available": True, "total_vram_mb": 8192, "used_vram_mb": 100, "free_vram_mb": 8092}), ""))
    plan = runtime.plan("ocr")
    assert [item["max_image_side"] for item in plan["attempts"]] == [1024, 768, 640]
    assert runtime.doctor()["checks"]["upstream_pinned"] is True


def test_preflight_records_original_size_and_required_headroom(tmp_path):
    image = tmp_path / "real.png"
    Image.new("RGB", (576, 1024)).save(image)
    snapshot = {"available": True, "total_vram_mb": 8192, "used_vram_mb": 500, "free_vram_mb": 7692, "cuda_processes": [], "aegis_services": {}}
    runtime = GreenBoostRuntime(_config(tmp_path), command_runner=lambda c, t: subprocess.CompletedProcess(c, 0, json.dumps(snapshot), ""))
    session = runtime.begin_ocr(image)
    assert session.original_image_size == [576, 1024]
    assert session.free_vram_before_inference_mb == 7692
    assert len(runtime.attempts()) == 3
