"""Web browser functionality for AEGIS."""

import httpx
from typing import Dict, Optional, Any
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import markdownify
except ImportError:
    markdownify = None


class WebBrowser:
    """Browser tool for fetching and summarizing web pages."""

    def __init__(self, core):
        """Initialize the WebBrowser."""
        self.core = core

    def fetch_url(self, url: str) -> Dict[str, Any]:
        """Fetch a URL and return its content."""
        try:
            response = httpx.get(
                url,
                timeout=30,
                trust_env=False,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AEGIS/0.1"
                }
            )
            
            title = None
            if BeautifulSoup is not None:
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string if soup.title else None

            if markdownify is not None:
                text_preview = markdownify.markdownify(response.text)[:3000]
            else:
                text_preview = response.text[:3000]
            
            return {
                "url": url,
                "status_code": response.status_code,
                "title": title,
                "text_preview": text_preview,
                "error": None,
                "final_url": str(response.url)
            }
        except Exception as e:
            return {
                "url": url,
                "status_code": None,
                "title": None,
                "text_preview": None,
                "error": str(e)
            }

    def summarize_url(self, url: str, profile: str = "general") -> str:
        """Summarize a URL using the core runtime."""
        # First fetch the URL
        result = self.fetch_url(url)
        
        if result["error"]:
            return f"Ошибка при получении страницы: {result['error']}"
        
        if not result["text_preview"]:
            return "Не удалось получить содержимое страницы"
            
        # Use core.runtime.chat to summarize
        prompt = f"Суммируй страницу на русском языке. Отвечай только на русском языке. Не показывай ход анализа. Не пиши 'First, I will'. Не пиши reasoning. Верни только итоговую сводку:\n\n{result['text_preview']}"
        
        try:
            summary = self.core.runtime.chat(
                prompt=prompt,
                profile=profile
            )
            return summary
        except Exception as e:
            return f"Ошибка при создании суммаризации: {str(e)}"
