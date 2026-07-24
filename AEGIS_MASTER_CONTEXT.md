# AEGIS Master Context

## Current Production Context

- Image Generation vertical completed.
- OCR Platform vertical active.
- Current sprint: Foundation.
- ComfyUI runs on Ubuntu in Docker.
- Service endpoints are resolved through the centralized AEGIS services configuration.
- Default Windows configuration: `F:\AI_WORKSPACE\config\services.yaml`.
- Internal backend observed: `18188` behind Caddy.
- Image outputs are stored on the Windows workspace at `F:\AI_WORKSPACE\images\generated`.
- Provider proxy issue fixed via LAN client handling with `trust_env=False`.
- First real PNG generation succeeded.
- OCR Platform Foundation is completed.
- Current OCR sprint connects `UnlimitedOCRProvider` through a Windows HTTP client and an Ubuntu/Docker service.
- OCR artifacts are stored on Windows at `F:\AI_WORKSPACE\ocr\results`.
- One Active Vertical principle remains mandatory.

## Image Generation Boundary

The completed production boundary is txt2img through AEGIS -> Workflow Library -> ComfyUI Provider -> ComfyUI -> PNG -> artifact/events. Future image features such as img2img, inpainting, ControlNet, IP-Adapter, upscale, tattoo presets, and model/workflow installation remain planned expansion, not blockers for the current production txt2img vertical.

## OCR Platform Boundary

The active boundary is Unlimited-OCR Provider only: Provider API compatibility, LAN HTTP client, Docker service wrapper, recognition commands, doctor diagnostics, artifacts, events, and acceptance. The sprint must not start PaddleOCR, Tesseract, Vision Language Models, Qwen-VL, UI Graph, Memory, Companion, or System Intelligence.
