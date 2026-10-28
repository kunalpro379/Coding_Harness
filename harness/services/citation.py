import re
from typing import Dict, List, Set, Tuple


class CitationTracker:
    def __init__(self):
        self.sources: Dict[str, Dict[str, str]] = {}
        self.by_url: Dict[str, str] = {}

    def reset(self):
        self.sources.clear()
        self.by_url.clear()

    def cite(self, url: str, title: str, excerpts: List[str]) -> str:
        sid = self.by_url.get(url)
        if sid is None:
            sid = f"S{len(self.sources) + 1}"
            self.by_url[url] = sid
            self.sources[sid] = {"url": url, "title": title or url, "excerpt": ""}

        src = self.sources[sid]
        clean_excerpts = "\n".join(excerpts).strip()
        src["excerpt"] = (src["excerpt"] + "\n" + clean_excerpts).strip()[:2000]

        return f"[{sid}] {title or url}\nURL: {url}\n{clean_excerpts}"

    def check_citations(self, text: str) -> Tuple[Set[str], Set[str]]:
        cited = set(re.findall(r"\[(S\d+)\]", text))
        valid = cited & set(self.sources.keys())
        unknown = cited - set(self.sources.keys())
        return valid, unknown

    def format_sources_summary(self) -> str:
        if not self.sources:
            return ""
        lines = ["=== Verified Sources ==="]
        for sid, meta in self.sources.items():
            lines.append(f"[{sid}] {meta['title']} ({meta['url']})")
        return "\n".join(lines)


default_citation_tracker = CitationTracker()
