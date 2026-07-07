"""Provider interfaces for Retriever sources."""

from __future__ import annotations

import re
from typing import Any

from aegis.retriever.models import RetrievedDocument


URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+")


class BaseProvider:
    """Base contract for retriever providers."""

    def __init__(self, core: Any | None = None):
        self.core = core

    def search(self, query: str) -> list[RetrievedDocument]:
        return []

    def name(self) -> str:
        return self.__class__.__name__


class MemoryProvider(BaseProvider):
    """Retrieve documents from AEGIS memory."""

    def search(self, query: str) -> list[RetrievedDocument]:
        if self.core is None or not hasattr(self.core, "memory"):
            return []

        records = self.core.memory.search(query)
        documents: list[RetrievedDocument] = []
        for record in records:
            documents.append(
                RetrievedDocument(
                    source="memory",
                    title=str(getattr(record, "title", "Memory")),
                    url="",
                    content=str(getattr(record, "content", "") or ""),
                    score=0.8,
                    metadata={
                        "id": getattr(record, "id", None),
                        "memory_type": getattr(record, "type", None),
                        "tags": getattr(record, "tags", []),
                    },
                )
            )
        return documents


class WorkspaceProvider(BaseProvider):
    """Expose concise workspace context."""

    def search(self, query: str) -> list[RetrievedDocument]:
        if self.core is None or not hasattr(self.core, "workspace"):
            return []

        root = self.core.workspace.root()
        projects = self.core.workspace.list_projects()
        project_text = ", ".join(str(project) for project in projects) or "none"
        content = f"root: {root}\nprojects: {project_text}"

        return [
            RetrievedDocument(
                source="workspace",
                title="Workspace",
                url="",
                content=content,
                score=0.5,
                metadata={"project_count": len(projects)},
            )
        ]


class BrowserProvider(BaseProvider):
    """Fetch explicit URLs found in a query."""

    def search(self, query: str) -> list[RetrievedDocument]:
        if self.core is None or not hasattr(self.core, "web"):
            return []

        documents: list[RetrievedDocument] = []
        for url in self._find_urls(query):
            result = self.core.web.fetch_url(url)
            content = str(result.get("text_preview") or "").strip()
            if result.get("error") or not content:
                continue

            documents.append(
                RetrievedDocument(
                    source="browser",
                    title=str(result.get("title") or url),
                    url=url,
                    content=content,
                    score=1.0,
                    metadata={
                        "status_code": result.get("status_code"),
                        "final_url": result.get("final_url"),
                    },
                )
            )
        return documents

    def _find_urls(self, query: str) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []
        for match in URL_RE.findall(str(query or "")):
            url = match.rstrip(".,;:")
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls


class WebSearchProvider(BaseProvider):
    """Search the web through a core service or the built-in fallback."""

    def search(self, query: str) -> list[RetrievedDocument]:
        service = self._search_service()
        results = service.search(query, max_results=5)

        documents: list[RetrievedDocument] = []
        for result in results:
            documents.append(
                RetrievedDocument(
                    source="web_search",
                    title=str(self._value(result, "title", "Web result")),
                    url=str(self._value(result, "url", "")),
                    content=str(self._value(result, "snippet", "") or ""),
                    score=0.7,
                    metadata={"search_source": self._value(result, "source", None)},
                )
            )
        return documents

    def _search_service(self) -> Any:
        if self.core is not None:
            service = getattr(self.core, "web_search", None)
            if service is not None and hasattr(service, "search"):
                return service

            registry = getattr(self.core, "registry", None)
            if registry is not None and hasattr(registry, "get"):
                service = registry.get("web_search")
                if service is not None and hasattr(service, "search"):
                    return service

        from aegis.web.search import WebSearch

        return WebSearch()

    def _value(self, result: Any, key: str, default: Any = None) -> Any:
        if isinstance(result, dict):
            return result.get(key, default)
        return getattr(result, key, default)


class WikipediaProvider(BaseProvider):
    pass


class GitHubProvider(BaseProvider):
    pass


class HuggingFaceProvider(BaseProvider):
    pass


DEFAULT_PROVIDERS: tuple[type[BaseProvider], ...] = (
    MemoryProvider,
    WorkspaceProvider,
    BrowserProvider,
    WebSearchProvider,
    WikipediaProvider,
    GitHubProvider,
    HuggingFaceProvider,
)
