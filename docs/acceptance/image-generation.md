# Image Generation Acceptance Test

## Objective

Confirm the full production cycle:

User Prompt
-> ImageGenerationRuntime
-> Workflow Library
-> ComfyUI Provider
-> ComfyUI on Ubuntu
-> PNG
-> Project/Mission Artifact
-> Event Platform

## Preconditions

- Windows 11 workstation.
- AEGIS in `F:\AEGIS`.
- Workspace in `F:\AI_WORKSPACE`.
- Ubuntu server `192.168.1.7`.
- ComfyUI endpoint `http://192.168.1.7:8188`.
- Docker container `aegis-comfyui`.
- GPU NVIDIA RTX 3050 8 GB.
- At least one installed compatible checkpoint.
- At least one API-format workflow.
- Output directory exists at `F:\AI_WORKSPACE\images\generated`.
- Active project is allowed, but not required.

Current catalog note: `AnyLoRA Checkpoint` and `DreamShaper XL` are present as roadmap catalog entries, but the current catalog records `installed=false`. Do not treat either as the installed acceptance checkpoint unless detection later marks it installed. The acceptance run should use the actually installed test checkpoint referenced by the default ComfyUI workflow.

## Verification Commands

```powershell
python -m compileall aegis
python -m pytest

aegis image doctor --verbose
aegis image providers
aegis workflow list
aegis workflow validate default
aegis image models
aegis image generate "neo tribal tattoo sketch, black ink, clean white background" --provider comfyui
```

## Expected Results

- `compileall` passes.
- All default tests pass.
- `image doctor` shows Overall `READY`.
- ComfyUI `available=yes`.
- ComfyUI `default=yes`.
- Workflow `default` validates.
- A real PNG is created.
- PNG is not a stub placeholder.
- File exists in `F:\AI_WORKSPACE\images\generated`.
- Result contains `provider=comfyui`.
- Seed and workflow are recorded.
- Artifact is registered when active project/mission is available.
- Lifecycle events are published.
- Errors are not hidden by fallback to `stub`.

## Pass Criteria

The vertical is Production Ready only if:

- the full scenario passes;
- a real PNG is confirmed;
- tests are green;
- documentation is updated;
- RFC and roadmap are synchronized.

## Known Limitations

- Only the first compatible test checkpoint is required for this production pass.
- AnyLoRA and DreamShaper XL are present in the catalog, but may be uninstalled.
- img2img, inpainting, ControlNet, IP-Adapter, and upscale remain future expansion.
- Installer/Package Manager may be a later roadmap item if not yet implemented.
- Unverified capabilities are not claimed as production-ready.

## Future Expansion

These are subsequent improvements for the image subsystem, not blockers for the current txt2img vertical:

- AnyLoRA.
- DreamShaper XL.
- img2img.
- inpainting.
- ControlNet.
- IP-Adapter.
- upscale.
- tattoo workflow presets.
- model/workflow installer.

## External Acceptance Automation

The external acceptance test is guarded and must be requested explicitly:

```powershell
$env:AEGIS_RUN_COMFYUI_ACCEPTANCE = "1"
python -m pytest tests/test_image_generation_acceptance.py -m "acceptance and external"
```

Without `AEGIS_RUN_COMFYUI_ACCEPTANCE=1`, the test is skipped and does not contact ComfyUI.
