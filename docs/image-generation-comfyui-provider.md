# ComfyUI Provider

## Status

Production Ready for txt2img through the Image Generation Runtime.

## Runtime Boundary

AEGIS orchestrates the request on Windows and sends API-format ComfyUI workflows to the Ubuntu/Docker backend at `http://192.168.1.7:8188`. The provider patches common workflow inputs only: prompt, negative prompt, seed, steps, image size, and save prefix. It does not hard-code a checkpoint or custom node.

## Network Handling

LAN and local ComfyUI URLs use an HTTP client with proxy environment disabled (`trust_env=False`). This avoids Windows proxy settings incorrectly intercepting private LAN requests.

## Output and Metadata

Generated PNG files are persisted under `F:\AI_WORKSPACE\images\generated` by default. Results record provider, workflow, model family, seed, prompt data, generation time, output path, and artifact metadata. If an active project is available, AEGIS registers `image.generated` artifacts.

## Diagnostics

Use:

```powershell
aegis image doctor --verbose
```

The doctor checks the LAN endpoint, reverse proxy behavior, ComfyUI endpoints, workflow file, and output directory. The vertical is considered ready only when the configured endpoint is reachable and no production failure is hidden by the stub provider.
