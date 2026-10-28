"""SearXNG Local & Fallback Web Search Engine.

Zero API keys, zero cost, 100% privacy-respecting search aggregating
Google, DuckDuckGo, Brave, Wikipedia, arXiv, and GitHub documentation.
Supports local Docker instance (http://localhost:4000) with automatic public fallbacks.
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from ..tools.base import BaseTool

logger = logging.getLogger(__name__)

FALLBACK_INSTANCES = [
    "http://localhost:4000",
    "https://searx.be",
    "https://search.ononoki.org",
    "https://searx.tiekoetter.com",
    "https://searx.space",
]


class SearXNGSearchTool(BaseTool):
    """Local SearXNG search tool with auto-failover."""

    name = "searxng_search"
    description = (
        "Search the web via local SearXNG (or fallback instances) without API keys or costs. "
        "Aggregates results across Google, DuckDuckGo, Brave, GitHub, arXiv, and Wikipedia. "
        "Supports query parameters, category filtering ('general', 'it', 'science'), and time range."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search keywords or technical question.",
            },
            "categories": {
                "type": "string",
                "enum": ["general", "it", "science", "files"],
                "description": "Search category: 'it' for programming/GitHub, 'science' for papers, 'general' for broad web.",
            },
            "time_range": {
                "type": "string",
                "enum": ["day", "week", "month", "year"],
                "description": "Optional time filter to fetch recent results.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of search results to return (default: 8).",
            },
        },
        "required": ["query"],
    }

    def run(
        self,
        query: str,
        categories: str = "it",
        time_range: Optional[str] = None,
        limit: int = 8,
    ) -> str:
        params = {
            "q": query,
            "format": "json",
            "categories": categories,
        }
        if time_range:
            params["time_range"] = time_range

        query_str = urllib.parse.urlencode(params)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for base_url in FALLBACK_INSTANCES:
            endpoint = f"{base_url}/search?{query_str}"
            try:
                req = urllib.request.Request(endpoint, headers=headers)
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8", errors="replace"))
                        results = data.get("results", [])
                        if not results:
                            continue

                        formatted = [f"=== SearXNG Search Results ({base_url}) for '{query}' ==="]
                        for idx, item in enumerate(results[:limit], 1):
                            title = item.get("title", "No Title")
                            url = item.get("url", "")
                            content = item.get("content", "")
                            engine = item.get("engine", "web")
                            formatted.append(f"\n[{idx}] {title} ({engine})")
                            formatted.append(f"URL: {url}")
                            if content:
                                formatted.append(f"Snippet: {content}")

                        return "\n".join(formatted)
            except Exception as e:
                logger.debug(f"SearXNG instance {base_url} failed: {e}")
                continue

        # If all SearXNG instances fail, fallback to DuckDuckGo HTML scraper
        return self._fallback_ddg(query, limit)

    def _fallback_ddg(self, query: str, limit: int) -> str:
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.read(), "html.parser")
                results = []
                for a in soup.find_all("a", class_="result__url")[:limit]:
                    href = a.get("href", "")
                    title = a.get_text(strip=True)
                    results.append(f"- {title}: {href}")

                if results:
                    return f"=== Web Search Results (Fallback) for '{query}' ===\n" + "\n".join(results)
        except Exception as e:
            return f"Search failed across all providers: {e}"
        return f"No results found for '{query}'."

