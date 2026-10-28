"""Context Injection & Environment State Observers.

Generates late-injected dynamic context:
- System clock & active git branch
- Git status diffs (modified/added/deleted files)
- Active Multi-step Plan (<todos>)
This late injection block is appended at the tail of messages each turn,
ensuring the earlier messages remain byte-identical for KV-cache retention.
"""

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from ..core.config import settings
from ..core.types import Message, Role

GIT_LABELS = {
    "M": "modified",
    "A": "added",
    "D": "deleted",
    "??": "untracked (new)",
    "R": "renamed",
}


class ContextObserver:
    """Monitors repository changes and generates structured reminder prompt blocks."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or settings.workspace_root
        self._last_state: Dict[str, Tuple[str, Optional[str]]] = self._snapshot_git_state()

    def _run_git(self, args: str) -> str:
        try:
            res = subprocess.run(
                f"git {args}",
                shell=True,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return res.stdout.strip()
        except Exception:
            return ""

    def _file_hash(self, rel_path: str) -> Optional[str]:
        target = self.workspace_root / rel_path
        if target.is_file():
            try:
                return hashlib.md5(target.read_bytes()).hexdigest()
            except OSError:
                return None
        return None

    def _snapshot_git_state(self) -> Dict[str, Tuple[str, Optional[str]]]:
        state = {}
        output = self._run_git("status --porcelain")
        for line in output.splitlines():
            if len(line) < 4:
                continue
            status = line[:2].strip()
            path = line[3:].strip()
            state[path] = (status, self._file_hash(path))
        return state

    def detect_changes(self) -> Dict[str, str]:
        """Detect file status changes since the previous check."""
        current = self._snapshot_git_state()
        changed: Dict[str, str] = {}
        for path, (status, h) in current.items():
            if path not in self._last_state or self._last_state[path] != (status, h):
                changed[path] = status
        self._last_state = current
        return changed

    def build_injection(self, todos_text: Optional[str] = None) -> Message:
        """Construct the prompt injection block."""
        branch = self._run_git("branch --show-current") or "(detached / non-git)"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content_parts = [
            "<environment_context>",
            f"current_time: {now_str}",
            f"git_branch: {branch}",
            f"workspace: {self.workspace_root}",
            "</environment_context>",
        ]

        if todos_text:
            content_parts.append(f"\n<active_plan>\n{todos_text}\n</active_plan>")

        from .long_term import default_long_term_memory
        memory_block = default_long_term_memory.render_context_block()
        if memory_block:
            content_parts.append(f"\n{memory_block}")

        changes = self.detect_changes()
        if changes:
            lines = [f"- {path} [{GIT_LABELS.get(code, code)}]" for path, code in changes.items()]
            content_parts.append(
                "\n<system-reminder>\n"
                "The following files changed on disk since your previous turn. Re-read before editing:\n"
                + "\n".join(lines)
                + "\n</system-reminder>"
            )

        return Message(role=Role.USER, content="\n".join(content_parts))


observer = ContextObserver()
