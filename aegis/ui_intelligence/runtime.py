from __future__ import annotations

from typing import Any

from aegis.capabilities import CapabilityDescriptor
from aegis.serialization import to_plain

from .models import UIElement, UIObservation
from .providers import BrowserObservationProvider


class UIIntelligenceRuntime:
    """Observation layer that exposes a compact, provider-neutral UI model."""

    def __init__(self, core: Any):
        self.core = core

    def observe(self, payload: dict | None = None) -> UIObservation:
        return self._provider().observe()

    def describe(self, payload: dict | None = None) -> dict:
        observation = self.observe()
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

    def locate(self, query: str | dict | None = None, role: str | None = None) -> dict:
        query_text = self._query_text(query)
        if not query_text:
            raise ValueError("ui.locate requires a non-empty query")
        role = self._role_text(query, role)
        observation = self.observe()
        elements = observation.elements
        if role:
            elements = [
                element
                for element in elements
                if str(element.role or "").casefold() == role.casefold()
            ]
        matches = [
            {
                **to_plain(element),
                "score": self._score(element, query_text),
                "possible_actions": self._possible_actions(element, observation.actions),
            }
            for element in elements
            if self._score(element, query_text) > 0
        ]
        matches.sort(key=lambda item: item["score"], reverse=True)
        return {
            "query": query_text,
            "role": role,
            "source": observation.source,
            "url": observation.url,
            "title": observation.title,
            "best_match": matches[0] if matches else None,
            "matches": matches,
            "possible_actions": matches[0]["possible_actions"] if matches else [],
        }

    def register_capabilities(self) -> None:
        capability_runtime = getattr(self.core, "capability_runtime", None)
        if capability_runtime is None:
            return
        for descriptor, method in (
            (
                CapabilityDescriptor(
                    id="ui.observe",
                    name="Observe UI",
                    owner_agent="ui_intelligence",
                    permissions=["browser.read"],
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    tags=["ui", "observation", "browser"],
                    metadata={"provider_type": "runtime", "side_effects": []},
                ),
                "observe",
            ),
            (
                CapabilityDescriptor(
                    id="ui.describe",
                    name="Describe UI",
                    owner_agent="ui_intelligence",
                    permissions=["browser.read"],
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    tags=["ui", "observation", "browser"],
                    metadata={"provider_type": "runtime", "side_effects": []},
                ),
                "describe",
            ),
            (
                CapabilityDescriptor(
                    id="ui.locate",
                    name="Locate UI Element",
                    owner_agent="ui_intelligence",
                    permissions=["browser.read"],
                    input_schema={
                        "type": "object",
                        "required": ["query"],
                        "properties": {
                            "query": {"type": "string"},
                            "role": {"type": "string"},
                        },
                    },
                    output_schema={"type": "object"},
                    tags=["ui", "locate", "browser"],
                    metadata={"provider_type": "runtime", "side_effects": []},
                ),
                "locate",
            ),
        ):
            capability_runtime.unregister(descriptor.id)
            capability_runtime.register(
                descriptor,
                {
                    "type": "runtime",
                    "runtime": "ui_intelligence",
                    "method": method,
                },
            )

    def _provider(self) -> BrowserObservationProvider:
        browser = (
            self._browser_service()
            or getattr(self.core, "browser_provider", None)
            or self._browser_agent_provider()
        )
        if browser is None:
            raise RuntimeError("Browser service is not available.")
        return BrowserObservationProvider(browser)

    def _browser_service(self) -> Any | None:
        service_runtime = getattr(self.core, "service_runtime", None)
        registry = getattr(service_runtime, "registry", None)
        get_service = getattr(registry, "get", None)
        if callable(get_service):
            return get_service("browser-service")
        return None

    def _browser_agent_provider(self) -> Any | None:
        agent_runtime = getattr(self.core, "agent_runtime", None)
        registry = getattr(agent_runtime, "registry", None)
        get_agent = getattr(registry, "get", None)
        if callable(get_agent):
            agent = get_agent("browser-agent")
            return getattr(agent, "provider", None)
        return None

    def _query_text(self, query: str | dict | None) -> str:
        if isinstance(query, dict):
            query = query.get("query")
        return str(query or "").strip()

    def _role_text(self, query: str | dict | None, role: str | None = None) -> str | None:
        explicit_role = str(role or "").strip()
        if explicit_role:
            return explicit_role
        if isinstance(query, dict):
            payload_role = str(query.get("role") or "").strip()
            if payload_role:
                return payload_role
        return None

    def _score(self, element: UIElement, query: str) -> int:
        wanted = query.casefold()
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

    def _possible_actions(self, element: UIElement, actions: list[dict]) -> list[dict]:
        return [action for action in actions if action.get("target") == element.id]
