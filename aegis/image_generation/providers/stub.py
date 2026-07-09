"""Dependency-light image generation stub provider."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

from aegis.image_generation.models import (
    ImageGenerationRequest,
    ImageGenerationResult,
)

DEFAULT_OUTPUT_DIR = Path(r"F:\AI_WORKSPACE\images\generated")


class StubImageGenerationProvider:
    name = "stub"

    def available(self) -> bool:
        return True

    def capabilities(self) -> dict:
        return {
            "mode": "placeholder",
            "requires_model": False,
            "formats": ["png"],
            "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        }

    def generate(
        self,
        request: ImageGenerationRequest,
    ) -> ImageGenerationResult:
        output_dir = Path(request.output_dir) if request.output_dir else DEFAULT_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        seed = request.seed if request.seed is not None else self._seed_for(request.prompt)
        path = output_dir / f"image_{uuid4().hex}.png"

        image = self._placeholder(request, seed)
        image.save(path, format="PNG")
        return ImageGenerationResult(
            success=True,
            image_paths=[str(path)],
            provider=self.name,
            prompt=request.prompt,
            seed=seed,
            metadata={
                "placeholder": True,
                "width": request.width,
                "height": request.height,
                "steps": request.steps,
                "style": request.style,
                "negative_prompt": request.negative_prompt,
                "output_dir": str(output_dir),
            },
        )

    def _placeholder(self, request: ImageGenerationRequest, seed: int) -> Image.Image:
        width = max(64, int(request.width or 1024))
        height = max(64, int(request.height or 1024))
        digest = hashlib.sha256(f"{request.prompt}|{seed}".encode("utf-8")).digest()
        background = (digest[0], digest[1], digest[2])
        accent = (digest[3], digest[4], digest[5])
        image = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(image)

        band_height = max(48, height // 6)
        draw.rectangle((0, height - band_height, width, height), fill=(20, 20, 24))
        for index in range(0, width, max(12, width // 32)):
            shade = (
                (accent[0] + index) % 255,
                (accent[1] + index // 2) % 255,
                (accent[2] + index // 3) % 255,
            )
            draw.line((index, 0, width - index // 2, height), fill=shade, width=2)

        title = "AEGIS image generation stub"
        prompt = request.prompt.strip() or "<empty prompt>"
        text = f"{title}\n\n{prompt[:220]}\n\nseed: {seed}"
        font = ImageFont.load_default()
        margin = max(16, min(width, height) // 24)
        draw.multiline_text(
            (margin, height - band_height + margin // 2),
            text,
            fill=(245, 245, 245),
            font=font,
            spacing=4,
        )
        return image

    def _seed_for(self, prompt: str) -> int:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)
