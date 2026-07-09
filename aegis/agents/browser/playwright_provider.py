from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain
from aegis.ui_intelligence.models import UIObservation
from aegis.ui_intelligence.providers import BrowserObservationProvider
from aegis.ui_runtime import UIRuntime
from aegis.ui_runtime.providers import BrowserProvider


DEFAULT_SCREENSHOT_DIR = Path("F:/AI_WORKSPACE/browser/screenshots")


class PlaywrightProvider:
    """Playwright-backed browser session provider for BrowserAgent."""

    def __init__(self, screenshot_dir: Path | str = DEFAULT_SCREENSHOT_DIR):
        self.screenshot_dir = Path(screenshot_dir)
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._browser_name: str | None = None
        self._headless: bool | None = None
        self._downloads: list[dict] = []

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
            self._context = self._browser.new_context(accept_downloads=True)
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

    def inspect(self) -> dict:
        page = self._active_page()
        try:
            text = page.locator("body").inner_text(timeout=3000)
        except Exception:
            text = ""
        elements = self._dom_elements(page)
        result = {
            "url": page.url,
            "title": page.title(),
            "text_preview": text[:4000],
            "forms": self._dom_forms(page),
            "inputs": self._filter_elements(elements, tags={"input", "textarea", "select"}),
            "buttons": self._filter_elements(elements, tags={"button"}, roles={"button"}),
            "links": self._filter_elements(elements, tags={"a"}, roles={"link"}),
            "headings": self._filter_elements(
                elements,
                tags={"h1", "h2", "h3", "h4", "h5", "h6"},
                roles={"heading"},
            ),
        }
        try:
            result["ui_tree"] = to_plain(self.ui_tree())
        except Exception as exc:
            result["ui_tree_error"] = str(exc)
        return result

    def ui_tree(self) -> dict:
        return to_plain(self._ui_runtime().tree())

    def ui_observe(self) -> dict:
        return to_plain(BrowserObservationProvider(self).observe())

    def ui_describe(self) -> dict:
        observation = BrowserObservationProvider(self).observe()
        return self._observation_description(observation)

    def ui_locate(self, query: str) -> dict:
        observation = BrowserObservationProvider(self).observe()
        wanted = str(query or "").casefold()
        matches = [
            {
                **to_plain(element),
                "score": self._ui_score(element, wanted),
                "possible_actions": [
                    action
                    for action in observation.actions
                    if action.get("target") == element.id
                ],
            }
            for element in observation.elements
            if self._ui_score(element, wanted) > 0
        ]
        matches.sort(key=lambda item: item["score"], reverse=True)
        return {
            "query": query,
            "source": observation.source,
            "url": observation.url,
            "title": observation.title,
            "best_match": matches[0] if matches else None,
            "matches": matches,
            "possible_actions": matches[0]["possible_actions"] if matches else [],
        }

    def find(self, query: dict) -> dict:
        elements = self.elements().get("elements", [])
        matches = [
            {**element, "score": self._match_score(element, query)}
            for element in elements
            if self._matches_query(element, query)
        ]
        matches.sort(key=lambda item: item.get("score", 0), reverse=True)
        best_match = matches[0] if matches else None
        return {
            "matches": matches,
            "best_match": best_match,
            "suggested_selector": best_match.get("selector") if best_match else None,
        }

    def elements(self, limit: int = 50) -> dict:
        page = self._active_page()
        return {"elements": self._dom_elements(page, limit=limit)}

    def forms(self) -> dict:
        page = self._active_page()
        return {"forms": self._dom_forms(page)}

    def screenshot(self, path: str | None = None) -> dict:
        self._ensure_started()
        page = self._ensure_page()
        target = Path(path) if path else self._default_screenshot_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target), full_page=True)
        return {"path": str(target)}

    def click(self, selector: str) -> dict:
        page = self._active_page()
        page.locator(selector).click()
        return self._page_summary(page)

    def fill(self, selector: str, value: str) -> dict:
        page = self._active_page()
        page.locator(selector).fill(value)
        return self._page_summary(page)

    def press(self, key: str) -> dict:
        page = self._active_page()
        page.keyboard.press(key)
        return self._page_summary(page)

    def wait_for(self, selector: str | None = None, timeout_ms: int = 30000) -> dict:
        page = self._active_page()
        if selector:
            page.locator(selector).wait_for(timeout=timeout_ms)
            return {"selector": selector, "timeout_ms": timeout_ms, **self._page_summary(page)}
        page.wait_for_timeout(timeout_ms)
        return {"timeout_ms": timeout_ms, **self._page_summary(page)}

    def select(self, selector: str, value: str) -> dict:
        page = self._active_page()
        selected = page.locator(selector).select_option(value)
        return {"selected": selected, **self._page_summary(page)}

    def list_tabs(self) -> dict:
        self._ensure_started()
        if self._context is None:
            raise RuntimeError("Browser context is not available.")
        return {
            "tabs": [
                {
                    "index": index,
                    "url": page.url,
                    "title": page.title(),
                    "active": page == self._page,
                }
                for index, page in enumerate(self._context.pages)
            ]
        }

    def switch_tab(self, index: int) -> dict:
        page = self._tab_at(index)
        self._page = page
        page.bring_to_front()
        return {"index": index, **self._page_summary(page)}

    def close_tab(self, index: int | None = None) -> dict:
        self._ensure_started()
        if self._context is None:
            raise RuntimeError("Browser context is not available.")

        pages = list(self._context.pages)
        if not pages:
            return {"closed": False, "tabs": []}

        if index is None:
            target = self._page or pages[-1]
            closed_index = pages.index(target)
        else:
            closed_index = index
            target = self._tab_at(index)

        target.close()
        remaining = list(self._context.pages)
        self._page = remaining[min(closed_index, len(remaining) - 1)] if remaining else None
        return {"closed": True, "closed_index": closed_index, **self.list_tabs()}

    def download_start(self) -> dict:
        page = self._active_page()
        page.on("download", self._record_download)
        return {"listening": True, "downloads": list(self._downloads)}

    def upload(self, selector: str, path: str) -> dict:
        page = self._active_page()
        target = Path(path)
        page.locator(selector).set_input_files(str(target))
        return {"selector": selector, "path": str(target), **self._page_summary(page)}

    def status(self) -> dict:
        return {
            "running": self._browser is not None,
            "browser": self._browser_name,
            "headless": self._headless,
            "has_context": self._context is not None,
            "has_page": self._page is not None,
            "url": self._page.url if self._page is not None else None,
            "screenshot_dir": str(self.screenshot_dir),
            "downloads": list(self._downloads),
        }

    def _ensure_started(self) -> None:
        if self._browser is None:
            self.start()

    def _active_page(self):
        self._ensure_started()
        return self._ensure_page()

    def _ui_runtime(self) -> UIRuntime:
        return UIRuntime(BrowserProvider(self._active_page))

    def _ensure_page(self):
        if self._context is None:
            raise RuntimeError("Browser context is not available.")
        if self._page is None:
            self._page = self._context.new_page()
        return self._page

    def _tab_at(self, index: int):
        self._ensure_started()
        if self._context is None:
            raise RuntimeError("Browser context is not available.")
        pages = list(self._context.pages)
        if index < 0 or index >= len(pages):
            raise IndexError(f"Browser tab index out of range: {index}")
        return pages[index]

    def _page_summary(self, page) -> dict:
        return {"url": page.url, "title": page.title()}

    def _observation_description(self, observation: UIObservation) -> dict:
        interactive = [
            element
            for element in observation.elements
            if element.role in {"button", "link", "textbox", "combobox"}
        ]
        headings = [element for element in observation.elements if element.role == "heading"]
        return {
            "source": observation.source,
            "url": observation.url,
            "title": observation.title,
            "application": observation.application,
            "summary": observation.summary,
            "element_count": len(observation.elements),
            "interactive_count": len(interactive),
            "headings": [to_plain(element) for element in headings[:20]],
            "interactive": [to_plain(element) for element in interactive[:50]],
            "actions": observation.actions,
            "metadata": observation.metadata,
        }

    def _ui_score(self, element, wanted: str) -> int:
        score = 0
        for weight, value in (
            (25, element.name),
            (20, element.text),
            (10, element.role),
        ):
            current = str(value or "").casefold()
            if not current:
                continue
            if current == wanted:
                score += weight * 2
            elif wanted in current:
                score += weight
        if element.visible:
            score += 1
        if element.enabled:
            score += 1
        return score

    def _dom_elements(self, page, limit: int = 50) -> list[dict]:
        return page.evaluate(
            """
            (limit) => {
              const cssEscape = (value) => {
                if (window.CSS && CSS.escape) return CSS.escape(value);
                return String(value).replace(/["\\\\]/g, "\\\\$&");
              };
              const attrEscape = (value) => String(value).replace(/["\\\\]/g, "\\\\$&");
              const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.visibility !== "hidden" &&
                  style.display !== "none" &&
                  rect.width > 0 &&
                  rect.height > 0;
              };
              const ownText = (el) => {
                const text = (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
                return text.slice(0, 300);
              };
              const accessibleName = (el, text, placeholder, name, ariaLabel) => (
                ariaLabel ||
                el.getAttribute("title") ||
                placeholder ||
                el.getAttribute("value") ||
                text ||
                name ||
                ""
              );
              const selectorFor = (el, tag, text, placeholder, name) => {
                const id = el.getAttribute("id");
                if (id) return `#${cssEscape(id)}`;
                if (name) return `${tag}[name="${attrEscape(name)}"]`;
                if (placeholder) {
                  return `${tag}[placeholder="${attrEscape(placeholder)}"]`;
                }
                return { type: "text", value: { text: text.slice(0, 120), tag } };
              };
              const nodes = Array.from(document.querySelectorAll(
                "input, textarea, select, button, a, h1, h2, h3, h4, h5, h6, [role], [aria-label], [placeholder], [name]"
              ));
              return nodes.slice(0, limit).map((el) => {
                const tag = el.tagName.toLowerCase();
                const text = ownText(el);
                const placeholder = el.getAttribute("placeholder") || "";
                const ariaLabel = el.getAttribute("aria-label") || "";
                const name = el.getAttribute("name") || "";
                const selector = selectorFor(el, tag, text, placeholder, name);
                return {
                  tag,
                  text,
                  role: el.getAttribute("role") || "",
                  name: accessibleName(el, text, placeholder, name, ariaLabel),
                  placeholder,
                  aria_label: ariaLabel,
                  href: el.getAttribute("href") || "",
                  selector,
                  visible: visible(el),
                };
              });
            }
            """,
            limit,
        )

    def _dom_forms(self, page) -> list[dict]:
        return page.evaluate(
            """
            () => {
              const cssEscape = (value) => {
                if (window.CSS && CSS.escape) return CSS.escape(value);
                return String(value).replace(/["\\\\]/g, "\\\\$&");
              };
              const attrEscape = (value) => String(value).replace(/["\\\\]/g, "\\\\$&");
              const selectorFor = (el, tag) => {
                const id = el.getAttribute("id");
                const name = el.getAttribute("name");
                const placeholder = el.getAttribute("placeholder");
                if (id) return `#${cssEscape(id)}`;
                if (name) return `${tag}[name="${attrEscape(name)}"]`;
                if (placeholder) {
                  return `${tag}[placeholder="${attrEscape(placeholder)}"]`;
                }
                return { type: "text", value: { text: "", tag } };
              };
              return Array.from(document.forms).map((form, index) => ({
                index,
                action: form.getAttribute("action") || "",
                method: form.getAttribute("method") || "get",
                selector: form.id ? `#${cssEscape(form.id)}` : { type: "text", value: { tag: "form", index } },
                inputs: Array.from(form.querySelectorAll("input, textarea, select")).map((el) => {
                  const tag = el.tagName.toLowerCase();
                  const placeholder = el.getAttribute("placeholder") || "";
                  const ariaLabel = el.getAttribute("aria-label") || "";
                  const fieldName = el.getAttribute("name") || "";
                  return {
                    tag,
                    text: (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim(),
                    role: el.getAttribute("role") || "",
                    name: ariaLabel || el.getAttribute("title") || placeholder || fieldName || "",
                    placeholder,
                    aria_label: ariaLabel,
                    href: "",
                    selector: selectorFor(el, tag),
                    visible: true,
                    type: el.getAttribute("type") || "",
                  };
                }),
              }));
            }
            """
        )

    def _filter_elements(
        self,
        elements: list[dict],
        *,
        tags: set[str],
        roles: set[str] | None = None,
    ) -> list[dict]:
        roles = roles or set()
        return [
            element
            for element in elements
            if element.get("tag") in tags or element.get("role") in roles
        ]

    def _matches_query(self, element: dict, query: dict) -> bool:
        checks = {
            "text": self._contains(element.get("text"), query.get("text")),
            "role": self._contains(element.get("role"), query.get("role")),
            "placeholder": self._contains(
                element.get("placeholder"),
                query.get("placeholder"),
            ),
            "name": self._contains(element.get("name"), query.get("name")),
            "tag": self._equals(element.get("tag"), query.get("tag")),
        }
        requested = [key for key, value in query.items() if value not in (None, "")]
        return bool(requested) and all(checks.get(key, True) for key in requested)

    def _match_score(self, element: dict, query: dict) -> int:
        score = 0
        for key in ("text", "role", "placeholder", "name", "tag"):
            wanted = query.get(key)
            if wanted in (None, ""):
                continue
            current = str(element.get(key) or "")
            if current.lower() == str(wanted).lower():
                score += 10
            elif str(wanted).lower() in current.lower():
                score += 5
        if element.get("visible"):
            score += 1
        return score

    def _contains(self, current: Any, wanted: Any) -> bool:
        if wanted in (None, ""):
            return True
        return str(wanted).lower() in str(current or "").lower()

    def _equals(self, current: Any, wanted: Any) -> bool:
        if wanted in (None, ""):
            return True
        return str(current or "").lower() == str(wanted).lower()

    def _record_download(self, download) -> None:
        try:
            self._downloads.append(
                {
                    "suggested_filename": download.suggested_filename,
                    "url": download.url,
                }
            )
        except Exception:
            return

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
        self._downloads = []


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
