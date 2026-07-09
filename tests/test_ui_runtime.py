from aegis.ui_runtime import UIRuntime
from aegis.ui_runtime.providers import BrowserProvider


class FakeAccessibility:
    def __init__(self, snapshot):
        self.snapshot_data = snapshot

    def snapshot(self, interesting_only=False):
        return self.snapshot_data


class FakePage:
    url = "https://example.test/search"

    def __init__(self, snapshot):
        self.accessibility = FakeAccessibility(snapshot)


def test_browser_provider_converts_accessibility_snapshot_to_ui_tree():
    page = FakePage(
        {
            "role": "WebArea",
            "name": "Example",
            "children": [
                {"role": "heading", "name": "Welcome"},
                {"role": "textbox", "name": "Search", "disabled": False},
            ],
        }
    )

    tree = BrowserProvider(lambda: page).tree()

    assert tree.provider == "browser.playwright"
    assert tree.source == "https://example.test/search"
    assert tree.root.role == "WebArea"
    assert tree.root.children[1].id == "ui-0.1"
    assert tree.root.children[1].name == "Search"
    assert tree.root.children[1].enabled is True


def test_ui_runtime_describes_and_locates_elements():
    page = FakePage(
        {
            "role": "WebArea",
            "name": "Example",
            "children": [
                {"role": "button", "name": "Search"},
                {"role": "link", "name": "Docs"},
            ],
        }
    )
    runtime = UIRuntime(BrowserProvider(lambda: page))

    description = runtime.describe()
    located = runtime.locate("Search")

    assert description["element_count"] == 3
    assert description["interactive_count"] == 2
    assert located["best_match"]["role"] == "button"
    assert located["best_match"]["name"] == "Search"
