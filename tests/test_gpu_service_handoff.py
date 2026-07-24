from __future__ import annotations

import json
import subprocess

from aegis.compute import GPUServiceHandoff, select_service_for_task_type


def test_handoff_selects_service_by_task_type_without_llm():
    assert select_service_for_task_type("ocr.recognize_image") == "unlimited-ocr"
    assert select_service_for_task_type("image.generate") == "comfyui"
    assert select_service_for_task_type("shell.command") == ""


def test_ocr_handoff_stops_comfyui_before_starting_unlimited(tmp_path, monkeypatch):
    config_path = tmp_path / "gpu_services.json"
    config_path.write_text(json.dumps(_config()), encoding="utf-8")
    commands = []

    def runner(command: str, timeout: float):
        commands.append(command)
        stdout = "8192" if command == "free-vram" else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(GPUServiceHandoff, "_wait_for_health", lambda *args, **kwargs: True)

    report = GPUServiceHandoff(config_path, command_runner=runner, sleep=lambda _: None).prepare_for_task(
        "ocr.recognize_image"
    )

    assert report.target_service == "unlimited-ocr"
    assert report.stopped_services == ["comfyui"]
    assert commands == ["stop-comfyui", "free-vram", "start-unlimited"]


def test_image_handoff_stops_ocr_before_starting_comfyui(tmp_path, monkeypatch):
    config_path = tmp_path / "gpu_services.json"
    config_path.write_text(json.dumps(_config()), encoding="utf-8")
    commands = []

    def runner(command: str, timeout: float):
        commands.append(command)
        stdout = "8192" if command == "free-vram" else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(GPUServiceHandoff, "_wait_for_health", lambda *args, **kwargs: True)

    report = GPUServiceHandoff(config_path, command_runner=runner, sleep=lambda _: None).prepare_for_task(
        "image.generate"
    )

    assert report.target_service == "comfyui"
    assert report.stopped_services == ["unlimited-ocr"]
    assert commands == ["stop-unlimited", "free-vram", "start-comfyui"]


def test_image_handoff_unloads_ocr_before_stopping_it(tmp_path, monkeypatch):
    calls = []
    config = _config()
    config["services"]["unlimited-ocr"]["unload_url"] = "http://ocr.test/unload"
    config_path = tmp_path / "gpu_services.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    class Response:
        status_code = 200

        def json(self):
            return {"success": True}

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url):
            calls.append(("post", url))
            return Response()

        def get(self, url):
            return Response()

    monkeypatch.setattr("aegis.compute.gpu_service_handoff.httpx.Client", Client)

    def run(command, timeout):
        calls.append(("command", command))
        return subprocess.CompletedProcess(command, 0, "", "")

    report = GPUServiceHandoff(config_path, command_runner=run, sleep=lambda _: None).prepare_for_image()

    assert report.unloaded_services == ["unlimited-ocr"]
    assert calls.index(("post", "http://ocr.test/unload")) < calls.index(("command", "stop-unlimited"))


def test_ocr_handoff_can_warmup_after_health(tmp_path, monkeypatch):
    config = _config()
    config["services"]["unlimited-ocr"]["warmup_url"] = "http://ocr.test/warmup"
    config["services"]["unlimited-ocr"]["warmup_on_start"] = True
    config_path = tmp_path / "gpu_services.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.setattr(GPUServiceHandoff, "_wait_for_health", lambda *args, **kwargs: True)
    monkeypatch.setattr(GPUServiceHandoff, "_post_warmup", lambda *args, **kwargs: True)

    report = GPUServiceHandoff(
        config_path,
        command_runner=lambda command, timeout: subprocess.CompletedProcess(command, 0, stdout="8192", stderr=""),
        sleep=lambda _: None,
    ).prepare_for_task("ocr.recognize_image")

    assert report.health_ok is True
    assert report.warmup_url == "http://ocr.test/warmup"
    assert report.warmup_ok is True


def test_handoff_disabled_does_not_execute_commands(tmp_path):
    config = _config()
    config["enabled"] = False
    config_path = tmp_path / "gpu_services.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    commands = []

    report = GPUServiceHandoff(
        config_path,
        command_runner=lambda command, timeout: commands.append(command),
    ).prepare_for_task("ocr.recognize_image")

    assert report.skipped_reason == "gpu service handoff disabled"
    assert commands == []


def _config():
    return {
        "enabled": True,
        "task_mapping": {
            "ocr.": "unlimited-ocr",
            "image.": "comfyui",
        },
        "minimum_free_vram_mb": 1,
        "vram_check_command": "free-vram",
        "services": {
            "unlimited-ocr": {
                "health_url": "http://ocr.test/health",
                "conflicting_services": ["comfyui"],
                "start_command": "start-unlimited",
                "stop_command": "stop-unlimited",
            },
            "comfyui": {
                "health_url": "http://comfy.test/system_stats",
                "conflicting_services": ["unlimited-ocr"],
                "start_command": "start-comfyui",
                "stop_command": "stop-comfyui",
            },
        },
    }
