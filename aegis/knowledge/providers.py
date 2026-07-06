"""Knowledge provider adapters."""

from __future__ import annotations

import re
from typing import Any

from aegis.web.search import WebSearch

from .models import KnowledgeSource


URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+")
WEB_SEARCH_MARKERS = (
    "current",
    "latest",
    "recent",
    "today",
    "now",
    "news",
    "research",
    "compare",
    "comparison",
    "versus",
    "review",
    "price",
    "benchmark",
    " vs ",
    "\u0430\u043a\u0442\u0443\u0430\u043b",
    "\u0441\u0435\u0439\u0447\u0430\u0441",
    "\u0441\u0435\u0433\u043e\u0434\u043d\u044f",
    "\u043f\u043e\u0441\u043b\u0435\u0434\u043d",
    "\u043d\u043e\u0432\u043e\u0441\u0442",
    "\u0438\u0441\u0441\u043b\u0435\u0434",
    "\u0441\u0440\u0430\u0432\u043d",
    "\u043e\u0431\u0437\u043e\u0440",
    "\u0446\u0435\u043d",
    "\u0431\u0435\u043d\u0447\u043c\u0430\u0440\u043a",
)
INVALID_WEB_CONTENT_MARKERS = (
    "robot policy",
    "robots",
    "failed to fetch",
    "no readable text",
    "access denied",
    "captcha",
    "cloudflare",
)


def is_invalid_web_content(content: str) -> bool:
    normalized = str(content or "").lower()
    return any(marker in normalized for marker in INVALID_WEB_CONTENT_MARKERS)


class MemoryKnowledgeProvider:
    """Read relevant records from the public Memory API."""

    def __init__(self, core: Any):
        self.core = core

    def gather(self, query: str) -> list[KnowledgeSource]:
        try:
            records = self.core.memory.search(query)
        except Exception as exc:
            return [
                KnowledgeSource(
                    type="memory",
                    title="Memory unavailable",
                    content="",
                    score=0.0,
                    metadata={"error": str(exc)},
                )
            ]

        sources: list[KnowledgeSource] = []
        for record in records:
            content = str(getattr(record, "content", "") or "").strip()
            if not content:
                continue

            sources.append(
                KnowledgeSource(
                    type="memory",
                    title=str(getattr(record, "title", "Memory")),
                    content=content,
                    score=0.8,
                    metadata={
                        "id": getattr(record, "id", None),
                        "memory_type": getattr(record, "type", None),
                        "tags": getattr(record, "tags", []),
                    },
                )
            )

        return sources


class WebURLKnowledgeProvider:
    """Fetch explicit URLs found in a query."""

    def __init__(self, core: Any):
        self.core = core

    def find_urls(self, query: str) -> list[str]:
        seen = set()
        urls: list[str] = []
        for match in URL_RE.findall(query):
            url = match.rstrip(".,;:")
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def has_urls(self, query: str) -> bool:
        return bool(self.find_urls(query))

    def gather(self, query: str) -> list[KnowledgeSource]:
        sources: list[KnowledgeSource] = []
        for url in self.find_urls(query):
            try:
                result = self.core.web.fetch_url(url)
            except Exception as exc:
                sources.append(
                    self._invalid_source(
                        title=url,
                        content="",
                        url=url,
                        metadata={
                            "error": str(exc),
                            "requested_url": url,
                        },
                    )
                )
                continue

            content = str(result.get("text_preview") or "").strip()
            title = str(result.get("title") or result.get("final_url") or url)
            metadata = {
                "status_code": result.get("status_code"),
                "error": result.get("error"),
                "requested_url": url,
            }
            if result.get("error") or not content or is_invalid_web_content(content):
                sources.append(
                    self._invalid_source(
                        title=title,
                        content=content,
                        url=str(result.get("final_url") or url),
                        metadata=metadata,
                    )
                )
                continue

            sources.append(
                KnowledgeSource(
                    type="web",
                    title=title,
                    content=content,
                    url=str(result.get("final_url") or url),
                    score=1.0,
                    valid=True,
                    metadata=metadata,
                )
            )

        return sources

    def _invalid_source(
        self,
        title: str,
        content: str,
        url: str,
        metadata: dict,
    ) -> KnowledgeSource:
        invalid_metadata = dict(metadata)
        invalid_metadata["invalid"] = True
        return KnowledgeSource(
            type="web",
            title=title,
            content=content,
            url=url,
            score=0.0,
            valid=False,
            error="invalid_or_blocked_source",
            metadata=invalid_metadata,
        )


class WebSearchKnowledgeProvider:
    """Search the web for research queries that do not include explicit URLs."""

    def __init__(self, core: Any, web_search: WebSearch | None = None):
        self.core = core
        self.web_search = web_search or WebSearch()
        self.url_provider = WebURLKnowledgeProvider(core)

    def should_search(self, query: str) -> bool:
        normalized = f" {str(query or '').lower()} "
        if self.url_provider.has_urls(normalized):
            return False
        return any(marker in normalized for marker in WEB_SEARCH_MARKERS)

    def gather(self, query: str) -> list[KnowledgeSource]:
        if not self.should_search(query):
            return []

        try:
            results = self.web_search.search(query, max_results=5)
        except Exception:
            return []

        sources: list[KnowledgeSource] = []
        for result in results[:3]:
            try:
                fetched = self.core.web.fetch_url(result.url)
            except Exception:
                continue

            content = str(fetched.get("text_preview") or "").strip()
            if fetched.get("error") or not content or is_invalid_web_content(content):
                continue

            title = str(
                fetched.get("title")
                or result.title
                or fetched.get("final_url")
                or result.url
            )
            sources.append(
                KnowledgeSource(
                    type="web_search",
                    title=title,
                    content=content,
                    url=str(fetched.get("final_url") or result.url),
                    score=0.9,
                    metadata={
                        "search_title": result.title,
                        "search_snippet": result.snippet,
                        "search_source": result.source,
                        "status_code": fetched.get("status_code"),
                    },
                )
            )

        return sources


class WorkspaceKnowledgeProvider:
    """Expose concise workspace context."""

    def __init__(self, core: Any):
        self.core = core

    def gather(self, query: str) -> list[KnowledgeSource]:
        try:
            workspace_root = self.core.workspace.root()
            projects = self.core.workspace.list_projects()
        except Exception as exc:
            return [
                KnowledgeSource(
                    type="workspace",
                    title="Workspace unavailable",
                    content="",
                    score=0.0,
                    metadata={"error": str(exc)},
                )
            ]

        lines = [f"workspace_root: {workspace_root}"]
        if projects:
            lines.append("projects: " + ", ".join(projects))
        else:
            lines.append("projects: none")

        return [
            KnowledgeSource(
                type="workspace",
                title="Workspace",
                content="\n".join(lines),
                score=0.5,
                metadata={"project_count": len(projects)},
            )
        ]
