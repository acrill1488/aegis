from __future__ import annotations

from typing import Any

from aegis.ui_intelligence.models import UIElement, UIObservation


class BrowserObservationProvider:
    """Build a compact UI observation from browser DOM and form inspection."""

    _IGNORED_TAGS = {"meta", "script", "style"}
    _TEXTBOX_INPUT_TYPES = {"", "text", "email", "search"}

    def __init__(self, browser: Any):
        self.browser = browser

    def observe(self) -> UIObservation:
        status = self._call("health") or self._call("status") or {}
        inspect_data = self._call_action("inspect", {}) or {}
        forms_data = self._call_action("forms", {}) or {}
        elements_data = inspect_data or self._call_action("elements", {"limit": 100}) or {}

        url = inspect_data.get("url") or self._status_value(status, "url")
        title = inspect_data.get("title")
        raw_elements = self._collect_elements(elements_data, forms_data)
        elements = self._to_elements(raw_elements)
        actions = self._actions(elements)
        focused = next(
            (element for element in elements if element.metadata.get("focused")),
            None,
        )
        return UIObservation(
            source="browser.dom",
            url=url,
            title=title,
            application="browser",
            focused_element=focused,
            elements=elements,
            actions=actions,
            summary=self._summary(title=title, url=url, elements=elements),
            metadata={
                "provider": "browser",
                "status": status,
                "raw_element_count": len(raw_elements),
                "visible_element_count": len(elements),
            },
        )

    def _call(self, name: str, *args: Any) -> Any:
        handler = getattr(self.browser, name, None)
        if not callable(handler):
            return None
        try:
            return handler(*args)
        except Exception:
            return None

    def _call_action(self, action: str, payload: dict) -> dict:
        invoke = getattr(self.browser, "invoke", None)
        if callable(invoke):
            try:
                return invoke(action, payload)
            except Exception:
                return {}

        handler_name = "extract_text" if action == "text" else action
        handler = getattr(self.browser, handler_name, None)
        if not callable(handler):
            return {}
        try:
            if action == "elements":
                return handler(int(payload.get("limit", 100)))
            return handler()
        except Exception:
            return {}

    def _status_value(self, status: dict, key: str) -> Any:
        provider = status.get("provider")
        if isinstance(provider, dict) and provider.get(key) is not None:
            return provider.get(key)
        return status.get(key)

    def _collect_elements(self, elements_data: dict, forms_data: dict) -> list[dict]:
        collected: list[dict] = []
        for key in ("inputs", "buttons", "links", "headings", "elements"):
            values = elements_data.get(key) or []
            if isinstance(values, list):
                collected.extend(item for item in values if isinstance(item, dict))

        for form in forms_data.get("forms") or []:
            if not isinstance(form, dict):
                continue
            for field in form.get("inputs") or []:
                if isinstance(field, dict):
                    collected.append({**field, "form": self._form_metadata(form)})
        return collected

    def _form_metadata(self, form: dict) -> dict:
        return {
            "index": form.get("index"),
            "action": form.get("action"),
            "method": form.get("method"),
            "selector": form.get("selector"),
        }

    def _to_elements(self, raw_elements: list[dict]) -> list[UIElement]:
        elements: list[UIElement] = []
        seen: set[tuple[str, str, str, str]] = set()
        for raw in raw_elements:
            if self._is_noise(raw):
                continue
            role = self._role(raw)
            if not role:
                continue
            name = self._name(raw)
            text = self._clean(raw.get("text"))
            selector = raw.get("selector")
            key = (role, name, text, str(selector))
            if key in seen:
                continue
            seen.add(key)
            element = UIElement(
                id=f"ui-{len(elements)}",
                role=role,
                name=name,
                text=text,
                selector=selector,
                visible=bool(raw.get("visible", True)),
                enabled=not bool(raw.get("disabled", False)),
                confidence=0.9 if raw.get("role") else 0.8,
                source="browser.dom",
                metadata=self._metadata(raw),
            )
            elements.append(element)
        return elements

    def _is_noise(self, raw: dict) -> bool:
        tag = str(raw.get("tag") or "").lower()
        if tag in self._IGNORED_TAGS:
            return True
        if tag == "input" and str(raw.get("type") or "").lower() == "hidden":
            return True
        if raw.get("visible") is False:
            return True
        text = self._clean(raw.get("text"))
        if len(text) > 200:
            return True
        if not any(
            self._clean(raw.get(key))
            for key in ("text", "name", "placeholder", "aria_label")
        ):
            return True
        return False

    def _role(self, raw: dict) -> str:
        tag = str(raw.get("tag") or "").lower()
        input_type = str(raw.get("type") or "").lower()
        if tag == "input" and input_type in self._TEXTBOX_INPUT_TYPES:
            return "textbox"
        if tag == "textarea":
            return "textbox"
        if tag == "button":
            return "button"
        if tag == "a":
            return "link"
        if tag in {"h1", "h2", "h3"}:
            return "heading"
        if tag == "select":
            return "combobox"
        return str(raw.get("role") or "").lower()

    def _name(self, raw: dict) -> str:
        for key in ("aria_label", "placeholder", "name", "text"):
            value = self._clean(raw.get(key))
            if value:
                return value
        return ""

    def _metadata(self, raw: dict) -> dict:
        return {
            key: value
            for key, value in raw.items()
            if key
            not in {
                "role",
                "name",
                "text",
                "selector",
                "visible",
                "disabled",
            }
        }

    def _actions(self, elements: list[UIElement]) -> list[dict]:
        actions = [
            {"type": "screenshot", "target": "page"},
            {"type": "extract_text", "target": "page"},
            {"type": "navigate", "target": "page"},
        ]
        for element in elements:
            if not element.visible:
                continue
            if element.role == "textbox":
                actions.append(
                    {"type": "fill", "target": element.id, "selector": element.selector}
                )
            if element.role in {"button", "link"}:
                actions.append(
                    {"type": "click", "target": element.id, "selector": element.selector}
                )
        return actions

    def _summary(
        self,
        *,
        title: str | None,
        url: str | None,
        elements: list[UIElement],
    ) -> str:
        lines = [f"Current page: {title or 'Untitled'}"]
        if url:
            lines[0] += f" ({url})"
        lines.append("Visible controls:")
        for element in elements[:30]:
            if element.role not in {"textbox", "button", "link", "combobox", "heading"}:
                continue
            label = element.name or element.text or element.id
            lines.append(f"- {element.role.title()}: {label}")
        return "\n".join(lines)

    def _clean(self, value: Any) -> str:
        return " ".join(str(value or "").split())
