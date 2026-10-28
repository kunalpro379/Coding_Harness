import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from ..core.config import settings
from ..services.citation import default_citation_tracker
from ..services.ledger import default_ledger
from ..services.tracer import default_tracer
from .base import BaseTool


def clean_html_to_markdown(html_content: str) -> str:
    clean = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<h[1-3][^>]*>(.*?)</h[1-3]>", r"\n### \1\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<(p|br|div)[^>]*>", "\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"""<a\s+(?:[^>]*?\s+)?href=["']([^"']*)["'][^>]*>(.*?)</a>""", r"[\2](\1)", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = html.unescape(clean)
    clean = re.sub(r"\n\s*\n+", "\n\n", clean)
    return clean.strip()


def parallel_api_post(endpoint: str, payload: dict, timeout: int = 15, attempts: int = 3) -> dict:
    api_key = settings.parallel_api_key or os.environ.get("PARALLEL_API_KEY")
    if not api_key:
        raise ValueError("Missing PARALLEL_API_KEY")

    url = f"https://api.parallel.ai/v1{endpoint}"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "CursorAgentHarness/2.0",
    }
    data_bytes = json.dumps(payload).encode("utf-8")

    err = ""
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except urllib.error.HTTPError as he:
            err = f"HTTP {he.code}: {he.read().decode('utf-8', errors='replace')[:250]}"
            if he.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(err)
        except Exception as ex:
            err = f"Network error: {type(ex).__name__} - {str(ex)}"

        time.sleep(2 ** i)

    raise RuntimeError(f"Parallel API call to {endpoint} failed after {attempts} attempts: {err}")


class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Search the web using Parallel Search API with source citation IDs [S1], [S2]. "
        "Supports mode='fast' (default) or 'advanced' for complex queries. Falls back to DuckDuckGo if no API key."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query or objective"},
            "mode": {
                "type": "string",
                "enum": ["fast", "advanced"],
                "description": "Parallel Search mode ('fast' is quick/cost-effective, 'advanced' for deep search)",
            },
            "max_results": {"type": "integer", "description": "Max results to return (default 5)"},
        },
        "required": ["query"],
    }

    def run(self, query: str, mode: str = None, max_results: int = 5) -> str:
        search_mode = mode or settings.parallel_search_mode or "fast"
        has_parallel_key = bool(settings.parallel_api_key or os.environ.get("PARALLEL_API_KEY"))

        if has_parallel_key:
            if not default_ledger.can_spend(0.005 if search_mode == "advanced" else 0.001):
                return "Error: Search budget limit reached for current session."

            try:
                payload = {
                    "objective": query,
                    "search_queries": [query],
                    "mode": search_mode,
                    "max_chars_total": 6000,
                    "advanced_settings": {
                        "max_results": min(max_results, 6),
                        "excerpt_settings": {"max_chars_per_result": 1500},
                    },
                }
                data = parallel_api_post("/search", payload, timeout=30 if search_mode == "advanced" else 15)
                default_ledger.charge_search(search_mode)

                formatted = []
                for item in data.get("results", []):
                    url = item.get("url", "")
                    title = item.get("title", "")
                    excerpts = item.get("excerpts", [])
                    entry = default_citation_tracker.cite(url, title, excerpts)
                    formatted.append(entry)

                out = f"=== Parallel Search ({search_mode}) ===\n\n" + "\n\n".join(formatted)
                default_tracer.log("search", mode=search_mode, query=query, results=len(formatted))
                return out
            except Exception as e:
                default_tracer.log("search_fallback", error=str(e), query=query)

        # Fallback to DuckDuckGo HTML search via POST (GET is blocked by DDG bot detection)
        try:
            post_data = urllib.parse.urlencode({"q": query}).encode("utf-8")
            req = urllib.request.Request(
                "https://html.duckduckgo.com/html/",
                data=post_data,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                html_body = response.read().decode("utf-8", errors="replace")

            raw_urls = re.findall(r'<a[^>]+class="result__url"[^>]*href="([^"]+)"', html_body, re.IGNORECASE)
            raw_snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html_body, re.DOTALL | re.IGNORECASE)

            entries = []
            count = min(len(raw_urls), max_results)
            for i in range(count):
                u = raw_urls[i].strip()
                s_raw = raw_snippets[i] if i < len(raw_snippets) else ""
                clean_snippet = re.sub(r"<[^>]+>", "", s_raw).strip()
                clean_snippet = html.unescape(clean_snippet)
                clean_snippet = clean_snippet.encode("ascii", "ignore").decode("ascii")
                cite_entry = default_citation_tracker.cite(u, u, [clean_snippet] if clean_snippet else ["Web search result"])
                entries.append(cite_entry)

            # If snippet tags are styled differently, fallback to result__url
            if not entries:
                raw_urls = re.findall(r'class="result__url"[^>]*href="([^"]+)"', html_body, re.IGNORECASE)
                for u in raw_urls[:max_results]:
                    entries.append(default_citation_tracker.cite(u.strip(), u.strip(), ["Web search result"]))

            if not entries:
                return f"No search results found for query: '{query}'."

            return f"=== Search Results for '{query}' ===\n\n" + "\n\n".join(entries)
        except Exception as e:
            return f"Search error for '{query}': {str(e)}"


class BrowserFetchTool(BaseTool):
    name = "browser_fetch"
    description = (
        "Extract clean readable text and documentation from web URLs with citation tracking. "
        "Leverages Parallel Extract API when configured or standard web scraping."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to extract content from"},
            "max_length": {"type": "integer", "description": "Maximum characters to return (default 8000)"},
        },
        "required": ["url"],
    }

    def run(self, url: str, max_length: int = 8000) -> str:
        if not (url.startswith("http://") or url.startswith("https://")):
            return "Error: URL must begin with http:// or https://"

        has_parallel_key = bool(settings.parallel_api_key or os.environ.get("PARALLEL_API_KEY"))
        if has_parallel_key:
            if not default_ledger.can_spend(0.001):
                return "Error: Extract budget limit reached for current session."
            try:
                payload = {
                    "urls": [url],
                    "max_chars_total": max_length,
                }
                data = parallel_api_post("/extract", payload, timeout=20)
                default_ledger.charge_extract(1)

                results = data.get("results", [])
                if results:
                    content = results[0].get("text", results[0].get("content", ""))
                    title = results[0].get("title", url)
                    cited = default_citation_tracker.cite(url, title, [content[:1500]])
                    return f"=== Parallel Extract: {url} ===\n\n{cited}\n\nFull Text:\n{content[:max_length]}"
            except Exception:
                pass

        # Native HTTP fallback
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw_bytes = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                raw_text = raw_bytes.decode(charset, errors="replace")

            formatted = clean_html_to_markdown(raw_text) if "text/html" in content_type else raw_text
            entry = default_citation_tracker.cite(url, url, [formatted[:1200]])

            if len(formatted) > max_length:
                return (
                    f"=== Web Page Content: {url} (Truncated) ===\n\n"
                    f"{entry}\n\n{formatted[:max_length]}\n\n[Truncated {len(formatted)-max_length} chars]"
                )
            return f"=== Web Page Content: {url} ===\n\n{entry}\n\n{formatted}"
        except Exception as e:
            return f"Error fetching URL '{url}': {type(e).__name__} - {str(e)}"
