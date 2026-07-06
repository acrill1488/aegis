from aegis.knowledge.providers import WebSearchKnowledgeProvider
from aegis.web.search import WebSearchResult


class FakeWebSearch:
    def search(self, query: str, max_results: int = 5):
        return [
            WebSearchResult(
                title=f"Result {index}",
                url=f"https://example.com/{index}",
                snippet=f"Snippet {index}",
            )
            for index in range(5)
        ]


class FakeWeb:
    def __init__(self):
        self.urls = []

    def fetch_url(self, url: str):
        self.urls.append(url)
        return {
            "title": f"Fetched {url}",
            "final_url": url,
            "status_code": 200,
            "text_preview": f"Content from {url}",
            "error": None,
        }


class FakeCore:
    def __init__(self):
        self.web = FakeWeb()


def test_web_search_provider_fetches_first_three_results_for_research_query():
    core = FakeCore()
    provider = WebSearchKnowledgeProvider(core, web_search=FakeWebSearch())

    sources = provider.gather("compare RTX 3090 vs RTX 4090")

    assert len(sources) == 3
    assert all(source.type == "web_search" for source in sources)
    assert all(source.score == 0.9 for source in sources)
    assert core.web.urls == [
        "https://example.com/0",
        "https://example.com/1",
        "https://example.com/2",
    ]


def test_web_search_provider_skips_queries_with_urls():
    core = FakeCore()
    provider = WebSearchKnowledgeProvider(core, web_search=FakeWebSearch())

    assert provider.gather("summarize https://example.com/page") == []
    assert core.web.urls == []
