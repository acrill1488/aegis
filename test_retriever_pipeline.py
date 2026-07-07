from dataclasses import dataclass
from pathlib import Path

from aegis.retriever.cleaner import Cleaner
from aegis.retriever.models import RetrievedDocument
from aegis.retriever.pipeline import RetrieverPipeline
from aegis.retriever.providers import (
    BrowserProvider,
    MemoryProvider,
    WebSearchProvider,
    WorkspaceProvider,
)
from aegis.retriever.ranker import Ranker
from aegis.retriever.summarizer import Summarizer


@dataclass
class FakeMemoryRecord:
    title: str
    content: str


@dataclass
class FakeSearchResult:
    title: str
    url: str
    snippet: str
    source: str = "fake"


class FakeMemory:
    def search(self, query: str):
        return [FakeMemoryRecord(title="Memory hit", content=f"stored {query}")]


class FakeWorkspace:
    def root(self):
        return Path("F:/AI_WORKSPACE")

    def list_projects(self):
        return ["alpha", "beta"]


class FakeWeb:
    def fetch_url(self, url: str):
        return {
            "title": "Fetched page",
            "text_preview": "Readable page text",
            "status_code": 200,
            "final_url": url,
            "error": None,
        }


class FakeWebSearch:
    def search(self, query: str, max_results: int = 5):
        return [
            FakeSearchResult(
                title="Search hit",
                url="https://example.com/search",
                snippet="search snippet",
            )
        ]


class FakeCore:
    memory = FakeMemory()
    workspace = FakeWorkspace()
    web = FakeWeb()
    web_search = FakeWebSearch()


def test_retriever_providers_map_core_services_to_documents():
    core = FakeCore()

    memory = MemoryProvider(core).search("query")
    workspace = WorkspaceProvider(core).search("query")
    web_search = WebSearchProvider(core).search("query")
    browser = BrowserProvider(core).search("open https://example.com")

    assert memory[0].source == "memory"
    assert memory[0].score == 0.8
    assert workspace[0].source == "workspace"
    assert "alpha" in workspace[0].content
    assert web_search[0].source == "web_search"
    assert web_search[0].score == 0.7
    assert browser[0].source == "browser"
    assert browser[0].score == 1.0


def test_clean_rank_and_summarize_contract():
    documents = [
        RetrievedDocument(
            source="workspace",
            title="Workspace",
            url="",
            content="root: F:/AI_WORKSPACE",
            score=0.5,
        ),
        RetrievedDocument(
            source="memory",
            title="Memory",
            url="",
            content="\nCAPTCHA\nremember this\n",
            score=0.8,
        ),
        RetrievedDocument(
            source="browser",
            title="Page",
            url="https://example.com",
            content="robot policy\n",
            score=1.0,
        ),
        RetrievedDocument(
            source="web_search",
            title="Search",
            url="https://example.com/search",
            content="search snippet",
            score=0.8,
        ),
    ]

    cleaned = Cleaner().clean(documents)
    ranked = Ranker().rank(cleaned)
    summary = Summarizer().summarize(ranked)

    assert [document.source for document in ranked] == [
        "web_search",
        "memory",
        "workspace",
    ]
    assert ranked[1].content == "remember this"
    assert "[web_search/Search]\nsearch snippet" in summary
    assert "[memory/Memory]\nremember this" in summary


def test_pipeline_uses_core_backed_default_providers():
    result = RetrieverPipeline(core=FakeCore()).retrieve("query")

    sources = {document.source for document in result.documents}
    assert {"memory", "workspace", "web_search"}.issubset(sources)
    assert result.summary
