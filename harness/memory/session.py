"""Session persistence with JSONL event streaming, rewind support, and checkpointing."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from ..core.config import settings
from ..core.types import Message, Role


class SessionManager:
    """Manages appending and restoring conversation logs from disk."""

    def __init__(self, storage_dir: Optional[Path] = None):
        base = storage_dir or (Path.home() / ".agents" / "sessions")
        # Sanitize project folder name
        workspace_tag = str(settings.workspace_root).replace(":", "_").replace("\\", "_").replace("/", "_")
        self.session_dir = base / workspace_tag
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._written_count = 0

    def _file_path(self, session_id: str) -> Path:
        return self.session_dir / f"{session_id}.jsonl"

    def save(self, messages: List[Message]):
        """Append only unwritten messages to the current session log."""
        if self._written_count >= len(messages):
            return

        target_file = self._file_path(self.current_session_id)
        with open(target_file, "a", encoding="utf-8") as f:
            for msg in messages[self._written_count:]:
                f.write(json.dumps(msg.to_dict()) + "\n")

        self._written_count = len(messages)

    def record_rewind(self, target_count: int):
        """Append a rewind event marker so past entries are preserved in log."""
        target_file = self._file_path(self.current_session_id)
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "rewind_to", "count": target_count}) + "\n")
        self._written_count = target_count

    def record_compaction(self, messages: List[Message]):
        """Persist compacted transcript checkpoint."""
        target_file = self._file_path(self.current_session_id)
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": "compacted",
                "messages": [m.to_dict() for m in messages],
            }) + "\n")
        self._written_count = len(messages)

    def load_session(self, session_id: str) -> List[Message]:
        """Replay session JSONL history with support for rewinds and compactions."""
        path = self._file_path(session_id)
        if not path.exists():
            return []

        raw_messages: List[Dict] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("event") == "rewind_to":
                    raw_messages = raw_messages[:entry["count"]]
                elif entry.get("event") == "compacted":
                    raw_messages = list(entry["messages"])
                else:
                    raw_messages.append(entry)

        self.current_session_id = session_id
        self._written_count = len(raw_messages)

        parsed_messages = []
        for d in raw_messages:
            try:
                parsed_messages.append(Message(**d))
            except Exception:
                pass
        return parsed_messages

    def list_sessions(self) -> List[Dict[str, str]]:
        """List all previous sessions sorted by newest first."""
        files = sorted(self.session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        results = []
        for file in files:
            session_id = file.stem
            # Derive preview title from first user message
            title = "(Empty session)"
            try:
                with open(file, "r", encoding="utf-8") as f:
                    for line in f:
                        entry = json.loads(line)
                        if entry.get("role") == "user":
                            title = str(entry.get("content", ""))[:60]
                            break
            except Exception:
                pass
            results.append({"id": session_id, "title": title, "path": str(file)})
        return results


session_manager = SessionManager()
