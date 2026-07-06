"""Web search provider for AEGIS."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import httpx


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = "duckduckgo"


class _DuckDuckGoHTMLParser(HTMLParser):
    """Extract search results from DuckDuckGo HTML and Lite pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._active_link: dict[str, str] | None = None
        self._active_snippet: list[str] | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        classes = set(attr_map.get("class", "").split())

        if tag == "a":
            href = attr_map.get("href", "")
            if self._is_result_link(href, classes):
                self._active_link = {"href": href, "title": ""}

        if tag in {"a", "td", "div", "span"} and (
            "result__snippet" in classes or "result-snippet" in classes
        ):
            self._active_snippet = []

    def handle_data(self, data: str) -> None:
        if self._active_link is not None:
            self._active_link["title"] += data
        if self._active_snippet is not None:
            self._active_snippet.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active_link is not None:
            title = self._clean_text(self._active_link["title"])
            url = self._normalize_url(self._active_link["href"])
            if title and url:
                self.results.append({"title": title, "url": url, "snippet": ""})
            self._active_link = None

        if tag in {"a", "td", "div", "span"} and self._active_snippet is not None:
            snippet = self._clean_text(" ".join(self._active_snippet))
            if snippet and self.results and not self.results[-1].get("snippet"):
                self.results[-1]["snippet"] = snippet
            self._active_snippet = None

    def _is_result_link(self, href: str, classes: set[str]) -> bool:
        if "result__a" in classes or "result-link" in classes:
            return True
        return bool(href and "/l/?" in href and "uddg=" in href)

    def _normalize_url(self, href: str) -> str:
        href = unescape(href or "")
        if not href:
            return ""

        absolute = urljoin("https://duckduckgo.com", href)
        parsed = urlparse(absolute)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            return unquote(target)
        return absolute

    def _clean_text(self, value: str) -> str:
        return " ".join(unescape(value or "").split())


class WebSearch:
    """Search the web using DuckDuckGo's public HTML endpoints."""

    _ENDPOINTS = (
        "https://lite.duckduckgo.com/lite/?q={query}",
        "https://html.duckduckgo.com/html/?q={query}",
    )

    def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        clean_query = str(query or "").strip()
        if not clean_query or max_results <= 0:
            return []

        limit = max(1, max_results)
        headers = {"User-Agent": "AEGIS/0.1"}

        try:
            with httpx.Client(
                timeout=30,
                trust_env=False,
                follow_redirects=True,
                headers=headers,
            ) as client:
                for endpoint in self._ENDPOINTS:
                    response = client.get(
                        endpoint.format(query=quote_plus(clean_query))
                    )
                    if response.status_code >= 400:
                        continue

                    results = self._parse(response.text, limit)
                    if results:
                        return results
        except Exception:
            return []

        return []

    def _parse(self, html: str, limit: int) -> list[WebSearchResult]:
        parser = _DuckDuckGoHTMLParser()
        try:
            parser.feed(html)
        except Exception:
            return []

        results: list[WebSearchResult] = []
        seen_urls: set[str] = set()
        for item in parser.results:
            url = item.get("url", "").strip()
            title = item.get("title", "").strip()
            if not url or not title or url in seen_urls:
                continue

            seen_urls.add(url)
            results.append(
                WebSearchResult(
                    title=title,
                    url=url,
                    snippet=item.get("snippet", "").strip(),
                )
            )
            if len(results) >= limit:
                break

        return results
