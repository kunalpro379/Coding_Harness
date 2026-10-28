"""Long-Term Fact & Developer Preference Memory Store (Mem0 Compatible).

Maintains cross-session persistent facts, developer instructions, and codebase quirks.
Persists to disk with semantic lookup, tag-based categorization, and auto-injection.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ..core.config import settings
from ..tools.base import BaseTool

logger = logging.getLogger(__name__)


class MemoryEntry(BaseModel):
    id: str
    fact: str
    category: str = "preference"  # preference, architecture, credential_rule, bug_fix
    source: str = "user_explicit"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class LongTermMemoryStore:
    """Persistent storage engine for user instructions and tech-stack preferences across runs."""

    def __init__(self, storage_path: Optional[Path] = None):
        base_dir = storage_path or (Path.home() / ".agents" / "memory")
        base_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = base_dir / "long_term_memories.json"
        self._memories: List[MemoryEntry] = []
        self._load()

    def _load(self):
        if not self.file_path.exists():
            self._memories = []
            return
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            self._memories = [MemoryEntry(**item) for item in data]
        except Exception as e:
            logger.warning(f"Failed to load long-term memories: {e}")
            self._memories = []

    def save(self):
        try:
            data = [m.model_dump() for m in self._memories]
            self.file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to persist long-term memory: {e}")

    def add_memory(self, fact: str, category: str = "preference", source: str = "user_explicit") -> MemoryEntry:
        import uuid
        entry = MemoryEntry(
            id=f"mem_{uuid.uuid4().hex[:8]}",
            fact=fact.strip(),
            category=category,
            source=source,
        )
        self._memories.append(entry)
        self.save()
        return entry

    def search_memories(self, query: str = "", limit: int = 5) -> List[MemoryEntry]:
        """Simple keyword-ranking search across stored facts."""
        if not query:
            return self._memories[-limit:]

        tokens = set(query.lower().split())
        scored = []
        for mem in self._memories:
            fact_tokens = set(mem.fact.lower().split())
            overlap = len(tokens.intersection(fact_tokens))
            if overlap > 0:
                scored.append((overlap, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            return [m for _, m in scored[:limit]]
        return self._memories[-limit:]

    def render_context_block(self, query: str = "") -> str:
        """Render relevant long-term memory facts for prompt injection."""
        relevant = self.search_memories(query, limit=5)
        if not relevant:
            return ""
        lines = ["<long_term_memory>"]
        for m in relevant:
            lines.append(f"- [{m.category.upper()}] {m.fact}")
        lines.append("</long_term_memory>")
        return "\n".join(lines)


default_long_term_memory = LongTermMemoryStore()


class RememberFactTool(BaseTool):
    """Tool allowing the agent or user to record a persistent developer preference or rule."""

    name = "remember_fact"
    description = (
        "Save a developer preference, coding convention, or project rule into permanent Long-Term Memory. "
        "This fact will be remembered across all future conversations, runs, and subagent dispatches."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "The specific instruction or rule (e.g. 'Always use forward slashes for file paths in scripts').",
            },
            "category": {
                "type": "string",
                "enum": ["preference", "architecture", "convention", "bug_fix"],
                "description": "Category for classifying the memory.",
            },
        },
        "required": ["fact"],
    }

    def __init__(self, store: Optional[LongTermMemoryStore] = None):
        self.store = store or default_long_term_memory

    def run(self, fact: str, category: str = "preference") -> str:
        entry = self.store.add_memory(fact=fact, category=category)
        return f"Fact permanently saved to Long-Term Memory (ID: {entry.id}): '{fact}'"


class RecallMemoriesTool(BaseTool):
    """Tool allowing the agent to explicitly search long-term memory."""

    name = "recall_memories"
    description = "Search stored developer preferences, conventions, and architectural facts from Long-Term Memory."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keywords or topic to search for (e.g. 'cmake', 'testing', 'coding style').",
            },
        },
    }

    def __init__(self, store: Optional[LongTermMemoryStore] = None):
        self.store = store or default_long_term_memory

    def run(self, query: str = "") -> str:
        results = self.store.search_memories(query=query, limit=8)
        if not results:
            return "No matching long-term memories found."
        formatted = ["=== Retrieved Long-Term Memories ==="]
        for r in results:
            formatted.append(f"• [{r.category}] {r.fact} (Saved: {r.timestamp[:10]})")
        return "\n".join(formatted)

