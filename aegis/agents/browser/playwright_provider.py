from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SCREENSHOT_DIR = Path("F:/AI_WORKSPACE/browser/screenshots")


class PlaywrightProvider:
    """Playwright-backed browser session provider for BrowserAgent v1."""

    def __init__(self, screenshot_dir: Path | str = DEFAULT_SCREENSHOT_DIR):
        self.screenshot_dir = Path(screenshot_dir)
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._browser_name: str | None = None
        self._headless: bool | None = None

    def start(self, headless: bool = False, browser: str = "firefox") -> dict:
        if browser != "firefox":
            raise RuntimeError("Browser Runtime v1 supports only Firefox.")
        if self._browser is not None:
            return self.status()

        sync_playwright, playwright_error = _load_playwright()
        try:
            self._playwright = sync_playwright().start()
            launcher = getattr(self._playwright, browser)
            self._browser = launcher.launch(headless=headless)
            self._context = self._browser.new_context()
        except playwright_error as exc:
            self._reset()
            raise RuntimeError(_playwright_runtime_error(str(exc))) from exc
        except Exception:
            self._reset()
            raise

        self._browser_name = browser
        self._headless = headless
        return self.status()

    def stop(self) -> dict:
        errors = []
        for resource in (self._context, self._browser):
            if resource is None:
                continue
            try:
                resource.close()
            except Exception as exc:
                errors.append(str(exc))
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as exc:
                errors.append(str(exc))
        self._reset()
        status = self.status()
        if errors:
            status["errors"] = errors
        return status

    def open(self, url: str | None = None) -> dict:
        self._ensure_started()
        page = self._ensure_page()
        if url:
            page.goto(url)
        return {"url": page.url, "title": page.title()}

    def navigate(self, url: str) -> dict:
        self._ensure_started()
        page = self._ensure_page()
        page.goto(url)
        return {"url": page.url, "title": page.title()}

    def extract_text(self) -> dict:
        self._ensure_started()
        page = self._ensure_page()
        try:
            text = page.locator("body").inner_text(timeout=3000)
        except Exception:
            text = ""
        return {
            "title": page.title(),
            "url": page.url,
            "text_preview": text[:4000],
        }

    def screenshot(self, path: str | None = None) -> dict:
        self._ensure_started()
        page = self._ensure_page()
        target = Path(path) if path else self._default_screenshot_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target), full_page=True)
        return {"path": str(target)}

    def status(self) -> dict:
        return {
            "running": self._browser is not None,
            "browser": self._browser_name,
            "headless": self._headless,
            "has_context": self._context is not None,
            "has_page": self._page is not None,
            "url": self._page.url if self._page is not None else None,
            "screenshot_dir": str(self.screenshot_dir),
        }

    def _ensure_started(self) -> None:
        if self._browser is None:
            self.start()

    def _ensure_page(self):
        if self._context is None:
            raise RuntimeError("Browser context is not available.")
        if self._page is None:
            self._page = self._context.new_page()
        return self._page

    def _default_screenshot_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return self.screenshot_dir / f"screenshot-{timestamp}.png"

    def _reset(self) -> None:
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._browser_name = None
        self._headless = None


def _load_playwright():
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install dependencies with "
            "`pip install -r requirements/base.txt`."
        ) from exc
    return sync_playwright, PlaywrightError


def _playwright_runtime_error(message: str) -> str:
    if "Executable doesn't exist" in message or "playwright install" in message:
        return (
            "Playwright browser binaries are not installed. Run "
            "`python -m playwright install firefox` and try again."
        )
    return message
