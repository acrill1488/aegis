from __future__ import annotations

from .models import Scenario, ScenarioStep


class ScenarioRegistry:
    """In-memory registry for replayable vertical scenarios."""

    def __init__(self):
        self._scenarios: dict[str, Scenario] = {}

    def register(self, scenario: Scenario) -> Scenario:
        if not scenario.id:
            raise ValueError("Scenario id is required")
        self._scenarios[scenario.id] = scenario
        return scenario

    def get(self, id: str) -> Scenario | None:
        return self._scenarios.get(id)

    def list(self) -> list[Scenario]:
        return [self._scenarios[key] for key in sorted(self._scenarios)]

    def seed_defaults(self) -> None:
        self.register(
            Scenario(
                id="browser.wikipedia.observe",
                name="Wikipedia Observe",
                description="Open Wikipedia and verify UI observation/locate.",
                steps=[
                    ScenarioStep(
                        id="open-wikipedia",
                        action="browser.open",
                        payload={"url": "https://www.wikipedia.org"},
                    ),
                    ScenarioStep(
                        id="observe-wikipedia",
                        action="ui.observe",
                        expect={"contains_text": "Wikipedia"},
                    ),
                    ScenarioStep(
                        id="locate-search",
                        action="ui.locate",
                        payload={"query": "Search"},
                        expect={"element_exists": True},
                    ),
                ],
            )
        )
        self.register(
            Scenario(
                id="browser.wikipedia.search",
                name="Wikipedia Search",
                description="Search Wikipedia for AEGIS and verify the result page text.",
                steps=[
                    ScenarioStep(
                        id="open-wikipedia",
                        action="browser.open",
                        payload={"url": "https://www.wikipedia.org"},
                    ),
                    ScenarioStep(
                        id="locate-search",
                        action="ui.locate",
                        payload={"query": "search"},
                        expect={"element_exists": True},
                    ),
                    ScenarioStep(
                        id="fill-search",
                        action="browser.fill",
                        payload={"selector": "#searchInput", "value": "AEGIS"},
                    ),
                    ScenarioStep(
                        id="press-enter",
                        action="browser.press",
                        payload={"key": "Enter"},
                    ),
                    ScenarioStep(id="wait", action="browser.wait"),
                    ScenarioStep(
                        id="read-text",
                        action="browser.text",
                        expect={"contains_text": "AEGIS"},
                    ),
                ],
            )
        )
