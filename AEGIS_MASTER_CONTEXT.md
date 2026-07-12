# AEGIS Master Context

## Current Production Context

- Image Generation vertical completed.
- OCR Platform vertical active.
- Current sprint: Foundation.
- ComfyUI runs on Ubuntu in Docker.
- Public endpoint: `http://192.168.1.7:8188`.
- Internal backend observed: `18188` behind Caddy.
- Image outputs are stored on the Windows workspace at `F:\AI_WORKSPACE\images\generated`.
- Provider proxy issue fixed via LAN client handling with `trust_env=False`.
- First real PNG generation succeeded.
- OCR Platform Foundation builds the provider-neutral runtime architecture before connecting any production OCR provider.
- One Active Vertical principle remains mandatory.

## Image Generation Boundary

The completed production boundary is txt2img through AEGIS -> Workflow Library -> ComfyUI Provider -> ComfyUI -> PNG -> artifact/events. Future image features such as img2img, inpainting, ControlNet, IP-Adapter, upscale, tattoo presets, and model/workflow installation remain planned expansion, not blockers for the current production txt2img vertical.

## OCR Platform Boundary

The active boundary is OCR Runtime foundation only: provider registry, Provider API, `OCRResult`, events, artifact registration, and CLI diagnostics. The sprint must not integrate OCR models, UnlimitedOCRProvider, PaddleOCRProvider, TesseractProvider, Vision, Qwen-VL, UI Graph, Memory, or Companion changes.
