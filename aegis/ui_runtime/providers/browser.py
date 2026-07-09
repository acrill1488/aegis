from __future__ import annotations

from typing import Any, Callable

from aegis.ui_runtime.models import UIElement, UITree


class BrowserProvider:
    """Playwright accessibility snapshot provider for Unified UI Tree."""

    def __init__(self, page_getter: Callable[[], Any]):
        self.page_getter = page_getter

    def tree(self) -> UITree:
        page = self.page_getter()
        snapshot = self._snapshot(page)
        root = self._element(snapshot or {}, path="0")
        return UITree(root=root, provider="browser.playwright", source=getattr(page, "url", ""))

    def _snapshot(self, page: Any) -> dict:
        accessibility = getattr(page, "accessibility", None)
        if accessibility is None:
            raise RuntimeError("Playwright accessibility snapshot is not available.")
        return accessibility.snapshot(interesting_only=False) or {}

    def _element(self, node: dict, path: str) -> UIElement:
        children = [
            self._element(child, f"{path}.{index}")
            for index, child in enumerate(node.get("children") or [])
            if isinstance(child, dict)
        ]
        metadata = {
            key: value
            for key, value in node.items()
            if key
            not in {
                "role",
                "name",
                "description",
                "value",
                "children",
                "disabled",
                "focused",
            }
        }
        if "focused" in node:
            metadata["focused"] = bool(node.get("focused"))
        return UIElement(
            id=f"ui-{path}",
            role=str(node.get("role") or ""),
            name=str(node.get("name") or ""),
            description=str(node.get("description") or ""),
            text=str(node.get("value") or node.get("name") or ""),
            bounds=node.get("bounds") if isinstance(node.get("bounds"), dict) else None,
            visible=not bool(node.get("hidden", False)),
            enabled=not bool(node.get("disabled", False)),
            children=children,
            metadata=metadata,
        )
