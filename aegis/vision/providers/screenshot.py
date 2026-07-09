"""Desktop screenshot provider for Vision v1."""

from __future__ import annotations

from typing import Any


class ScreenshotProvider:
    name = "screenshot"

    def __init__(self, core: Any):
        self.core = core

    def available(self) -> bool:
        return getattr(self.core, "desktop_runtime", None) is not None

    def capabilities(self) -> list[str]:
        return ["desktop.screenshot"]

    def capture(self) -> dict:
        desktop = getattr(self.core, "desktop_runtime", None)
        if desktop is None:
            raise RuntimeError("DesktopRuntime is required for screenshot capture.")
        return desktop.screenshot({})

    def analyze(self, image_path: str | None = None):
        raise NotImplementedError("ScreenshotProvider captures images only.")
