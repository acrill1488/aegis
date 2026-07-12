# AEGIS Master Context

## Current Production Context

- Image Generation vertical completed.
- ComfyUI runs on Ubuntu in Docker.
- Public endpoint: `http://192.168.1.7:8188`.
- Internal backend observed: `18188` behind Caddy.
- Image outputs are stored on the Windows workspace at `F:\AI_WORKSPACE\images\generated`.
- Provider proxy issue fixed via LAN client handling with `trust_env=False`.
- First real PNG generation succeeded.
- Next vertical: Unlimited-OCR, not yet started.
- One Active Vertical principle remains mandatory.

## Image Generation Boundary

The completed production boundary is txt2img through AEGIS -> Workflow Library -> ComfyUI Provider -> ComfyUI -> PNG -> artifact/events. Future image features such as img2img, inpainting, ControlNet, IP-Adapter, upscale, tattoo presets, and model/workflow installation remain planned expansion, not blockers for the current production txt2img vertical.
