"""Context Trimming, Output Spilling, and Strip Optimization.

1. Spilling & Capping: Fresh large tool output (e.g. huge git diff / build logs) is written to
   a temporary file on disk, showing only a preview window inline.
2. Turn-based Stripping: Once an agent turn concludes, historical tool outputs are reduced
   to compact stubs (300 chars) while maintaining the cached conversation prefix.
3. Drop Fitting: Emergency shedding of historical tool outputs if token limit is approached.
"""

import json
import tempfile
from pathlib import Path
from typing import List
from ..core.config import settings
from ..core.types import Message, Role

SUMMARY_TAG = "<summary>"
TRIMMED_PREFIX = "[output trimmed:"
_SPILLS: List[Path] = []


class ContextTrimmer:
    """Manages transcript size, cache retention, and temp file spills."""

    def __init__(
        self,
        cap_chars: int = None,
        stub_chars: int = None,
    ):
        self.cap_chars = cap_chars or settings.max_tool_output_chars
        self.stub_chars = stub_chars or settings.tool_stub_chars

    def spill_to_disk(self, text: str) -> str:
        """Persist full output to a temp file on disk for the duration of the current turn."""
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            prefix="harness-out-",
            suffix=".log",
            delete=False,
            encoding="utf-8",
        )
        temp_file.write(text)
        temp_file.close()
        path = Path(temp_file.name)
        _SPILLS.append(path)
        return str(path)

    def cap(self, text: str) -> str:
        """Cap fresh tool output if it exceeds max size, spilling the rest to disk."""
        if len(text) <= self.cap_chars:
            return text

        try:
            spill_path = self.spill_to_disk(text)
            excess = len(text) - self.cap_chars
            return (
                f"{text[:self.cap_chars]}\n\n"
                f"{TRIMMED_PREFIX} {excess} of {len(text)} chars cut. "
                f"Full output saved to: {spill_path}\n"
                f"Tip: Page through with 'bash' (head, tail, grep) during this turn.]"
            )
        except OSError:
            return text[:self.cap_chars] + f"\n\n{TRIMMED_PREFIX} {len(text) - self.cap_chars} chars cut.]"

    def sweep(self):
        """Purge temporary spilled files when turn ends."""
        global _SPILLS
        for path in _SPILLS:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        _SPILLS.clear()

    def find_locked_prefix_index(self, messages: List[Message]) -> int:
        """Find index where compaction summary locked prefix ends."""
        for idx in range(len(messages) - 1, -1, -1):
            content = messages[idx].content or ""
            if SUMMARY_TAG in content:
                return idx + 1
        return 0

    def strip_turn(self, messages: List[Message]) -> int:
        """Shrink completed turn tool results to stub length.
        
        Leaves the prefix cached while drastically reducing token load.
        """
        locked_idx = self.find_locked_prefix_index(messages)
        shrunk_count = 0

        for msg in messages[locked_idx:]:
            if msg.role != Role.TOOL:
                continue
            content = msg.content or ""
            if TRIMMED_PREFIX in content or len(content) <= self.stub_chars:
                continue

            msg.content = (
                f"{content[:self.stub_chars]}\n\n"
                f"{TRIMMED_PREFIX} {len(content) - self.stub_chars} characters trimmed. "
                f"Re-run command if full output is needed again.]"
            )
            shrunk_count += 1

        return shrunk_count

    def estimate_tokens(self, messages: List[Message]) -> int:
        """Heuristic token calculation: ~4 chars per token across JSON representation."""
        raw = json.dumps([m.to_dict() for m in messages])
        return len(raw) // 4

    def fit_budget(self, messages: List[Message], max_budget: int) -> int:
        """Emergency dropping of oldest tool results in unlocked region to fit token budget."""
        locked_idx = self.find_locked_prefix_index(messages)
        dropped = 0

        for msg in messages[locked_idx:]:
            if self.estimate_tokens(messages) <= max_budget:
                break
            if msg.role == Role.TOOL and TRIMMED_PREFIX not in (msg.content or ""):
                msg.content = f"{TRIMMED_PREFIX} output completely dropped to preserve context window.]"
                dropped += 1

        return dropped


trimmer = ContextTrimmer()
