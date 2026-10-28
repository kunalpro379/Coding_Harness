"""Specialized Critic & Reviewer Agent for validating changes and running test suites."""

from typing import List, Optional
from ..core.types import Message, Role
from ..providers.llm import LLMClient
from ..tools.base import ToolRegistry
from ..ui.terminal import TerminalUI
from .base import BaseAgent

REVIEWER_PROMPT = """
You are an uncompromising Code Reviewer & QA Specialist Agent.
Your duty is to rigorously review modifications, inspect git diffs, ensure test compliance,
and verify that no edge cases, regressions, or syntax errors were introduced.

Process:
1. Examine git status and recent diffs.
2. Review modified files for best practices, typing, and safety.
3. If unit tests exist or can be run via bash, verify their execution.
4. Output a concise assessment: Verdict (PASS/FAIL), identified risks, and required fixes.
"""


class ReviewerAgent(BaseAgent):
    """Subagent specialized in reviewing changes, checking tests, and asserting quality."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
    ):
        super().__init__(
            name="ReviewerAgent",
            role_description="Code QA and test validator",
            system_prompt=REVIEWER_PROMPT,
            llm=llm,
            tool_registry=tool_registry,
            ui_handler=ui_handler,
        )

    def run(self, review_scope: str) -> str:
        messages = [
            Message(role=Role.SYSTEM, content=self.system_prompt),
            Message(role=Role.USER, content=f"Review and validate this change: {review_scope}"),
        ]
        tools_schemas = self.registry.get_schemas(exclude=["write_todos", "task"])
        
        with self.ui.spinner("Reviewer agent validating modifications..."):
            response = self.llm.complete(messages, tools=tools_schemas)

        return response.message.content or "Review complete."
