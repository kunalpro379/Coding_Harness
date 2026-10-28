"""Transcript Compaction & Handoff Generation Engine.

When the transcript reaches threshold capacity (e.g. 82%), this agent generates a structured
handoff summary of everything accomplished so far, replaces historical messages up to a safe
tool boundary, and leaves an identical locked prefix for LLM prompt caching.
"""

import logging
from typing import List
from ..core.config import settings
from ..core.types import Message, Role, TokenUsage
from ..providers.llm import LLMClient
from .trimmer import trimmer

logger = logging.getLogger(__name__)

COMPACT_SYSTEM_PROMPT = """
You are the Compaction Agent for an enterprise AI Coding Harness.
The current session has expanded towards the edge of its context window.
Your mission is to author an authoritative handoff note that allows a fresh agent
to seamlessly resume the ongoing software engineering task without any context loss.

Format strictly with these Markdown headers:

## Goal
Exact user objectives and expectations.

## Work Completed & Decisions
Key implementation decisions taken, tools executed, and architectural rationale.
Explicitly document any failed approaches or dead ends so the successor agent does not repeat them.

## Files Touched
Bullet list of files inspected, created, or modified, with brief summaries of changes.

## System State
What functions properly, what tests or components are broken, what tasks remain incomplete.

## Immediate Next Steps
The concrete next operation to perform.

Guidelines:
- Cite exact file paths, class/function names, and error traces.
- No conversational filler or introductory greetings. Start directly with '## Goal'.
"""

HANDOFF_TEMPLATE = """<summary>
Notice: The prior conversation history has been compacted to preserve context tokens.
Below is the verified record of all previous work and system state. Treat this as your memory:

{summary}
</summary>"""


class Compactor:
    """Handles intelligent transcript summarization and context window pruning."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()

    def is_needed(self, usage: TokenUsage) -> bool:
        """Determines if the token count exceeds the threshold."""
        threshold = int(settings.context_window * settings.compact_at)
        return usage.prompt_tokens >= threshold

    def _render_transcript(self, messages: List[Message]) -> str:
        """Convert messages to plain textual transcript for summarization."""
        lines = []
        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue

            speaker = {
                Role.USER: "USER",
                Role.ASSISTANT: "ASSISTANT",
                Role.TOOL: "TOOL RESULT",
            }.get(msg.role, msg.role.value)

            content = msg.content or ""
            if msg.tool_calls:
                for call in msg.tool_calls:
                    content += f"\n[Executed: {call.function.name}({call.function.arguments})]"

            lines.append(f"### {speaker}:\n{content}")

        return "\n\n".join(lines)

    def _find_safe_boundary(self, messages: List[Message], start_idx: int) -> int:
        """Find the earliest message boundary that will not orphan tool responses."""
        start = max(1, start_idx)
        for idx in range(start, len(messages)):
            prev = messages[idx - 1]
            curr = messages[idx]
            # Don't split if current is a tool result or previous made tool calls
            if curr.role == Role.TOOL or (prev.tool_calls and len(prev.tool_calls) > 0):
                continue
            return idx
        return len(messages)

    def _calculate_tail_start(self, messages: List[Message], token_budget: int) -> int:
        """Walk backward from latest message until token budget for retained tail is filled."""
        running = 0
        for idx in range(len(messages) - 1, 0, -1):
            running += trimmer.estimate_tokens([messages[idx]])
            if running > token_budget:
                return self._find_safe_boundary(messages, idx)
        return self._find_safe_boundary(messages, 1)

    def compact(self, messages: List[Message]) -> List[Message]:
        """Summarizes past history, keeps system prompt + summary + recent tail."""
        target_tail_budget = int(settings.context_window * settings.compact_to)
        cut_index = self._calculate_tail_start(messages, target_tail_budget)

        if cut_index <= 1:
            logger.info("Transcript history is not long enough to warrant compaction.")
            return messages

        to_summarize = messages[1:cut_index]
        rendered = self._render_transcript(to_summarize)

        logger.info(f"Triggering transcript compaction across {len(to_summarize)} messages...")
        summary_response = self.llm.complete(
            messages=[
                Message(role=Role.SYSTEM, content=COMPACT_SYSTEM_PROMPT),
                Message(role=Role.USER, content=rendered),
            ],
            temperature=0.0,
        )

        handoff_content = HANDOFF_TEMPLATE.format(summary=summary_response.message.content)

        compacted_list = [
            messages[0],  # Keep original System prompt
            Message(role=Role.USER, content=handoff_content),
            *messages[cut_index:],  # Retain recent operational tail
        ]

        # Strip the tail to lock and maximize caching efficiency
        trimmer.strip_turn(compacted_list)
        return compacted_list


compactor = Compactor()
