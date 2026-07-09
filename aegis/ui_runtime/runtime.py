from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from .models import UIElement, UITree


class UIProvider(Protocol):
    def tree(self) -> UITree:
        ...


class UIRuntime:
    """Build and query a provider-neutral UI tree."""

    def __init__(self, provider: UIProvider):
        self.provider = provider

    def tree(self) -> UITree:
        return self.provider.tree()

    def describe(self) -> dict:
        tree = self.tree()
        elements = list(self._walk(tree.root))
        interactive = [
            element
            for element in elements
            if element.role in {"button", "link", "textbox", "combobox", "checkbox", "radio"}
        ]
        headings = [element for element in elements if element.role == "heading"]
        return {
            "provider": tree.provider,
            "source": tree.source,
            "root": self._element_summary(tree.root),
            "element_count": len(elements),
            "interactive_count": len(interactive),
            "headings": [self._element_summary(element) for element in headings[:20]],
            "interactive": [self._element_summary(element) for element in interactive[:50]],
        }

    def locate(self, query: str) -> dict:
        query = str(query or "").strip()
        if not query:
            raise ValueError("ui.locate requires a non-empty query")

        tree = self.tree()
        matches = [
            {
                **self._element_summary(element),
                "score": self._score(element, query),
            }
            for element in self._walk(tree.root)
            if self._score(element, query) > 0
        ]
        matches.sort(key=lambda item: item["score"], reverse=True)
        return {
            "query": query,
            "provider": tree.provider,
            "source": tree.source,
            "matches": matches,
            "best_match": matches[0] if matches else None,
        }

    def _walk(self, element: UIElement):
        yield replace(element, children=[])
        for child in element.children:
            yield from self._walk(child)

    def _element_summary(self, element: UIElement) -> dict:
        return {
            "id": element.id,
            "role": element.role,
            "name": element.name,
            "description": element.description,
            "text": element.text,
            "bounds": element.bounds,
            "visible": element.visible,
            "enabled": element.enabled,
            "metadata": dict(element.metadata),
        }

    def _score(self, element: UIElement, query: str) -> int:
        wanted = query.casefold()
        score = 0
        for weight, value in (
            (20, element.name),
            (15, element.text),
            (10, element.description),
            (5, element.role),
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
