"""Specialized Subagent for Read-Only Repository Exploration & Analysis.

Runs in an isolated ephemeral context window with a dedicated turn limit (MAX_TURNS).
Explores codebase via search_files, grep_code, read_file, and bash without mutating
files or touching the lead agent's plan or transcript.
Only its concise final synthesis report is returned to the lead agent.
"""

import json
from typing import List, Optional
from ..core.config import settings
from ..core.types import Message, Role, TokenUsage
from ..providers.llm import LLMClient
from ..tools.base import BaseTool, ToolRegistry
from ..ui.terminal import TerminalUI
from .base import BaseAgent

EXPLORATION_PROMPT = """
You are an expert Exploration Subagent.
A Lead Architect Agent dispatched you with a specific investigation question.
Your sole responsibility is to inspect the codebase, trace symbols, locate dependencies,
and report the verified architectural findings.

Operational Rules:
1. You operate in read-only mode. Never attempt to edit, delete, or write files.
2. Search in focused batches using grep_code, search_files, or read_file.
3. Stop exploring the instant you have gathered sufficient concrete evidence.
4. Your final reply is the ONLY message returned to the Lead Agent.
   Keep it concise (under 200 words).
   Cite EXACT file paths, line numbers, function signatures, and configuration settings.
   No conversational fluff or apologies.
"""


class ExplorationAgent(BaseAgent):
    """Subagent with isolated context executing in-depth code searches."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
        max_turns: Optional[int] = None,
    ):
        super().__init__(
            name="ExplorationAgent",
            role_description="Read-only repository detective",
            system_prompt=EXPLORATION_PROMPT,
            llm=llm,
            tool_registry=tool_registry,
            ui_handler=ui_handler,
        )
        self.max_turns = max_turns or settings.subagent_max_turns

    def run(self, query: str) -> str:
        """Execute independent exploration loop and return the final report."""
        # Clean isolated message transcript
        messages = [
            Message(role=Role.SYSTEM, content=self.system_prompt),
            Message(role=Role.USER, content=query),
        ]

        # Allowed tools for exploration subagent (structural guarantee: no editing tools, no planner)
        withheld = {"write_file", "str_replace", "write_todos", "task"}
        tools_schemas = self.registry.get_schemas(exclude=list(withheld))

        last_known_report = None

        for turn in range(1, self.max_turns + 1):
            with self.ui.spinner(f"Subagent investigating turn {turn}/{self.max_turns}..."):
                response = self.llm.complete(messages, tools=tools_schemas)

            msg = response.message
            messages.append(msg)
            if msg.content:
                last_known_report = msg.content

            # Subagent concluded and provided pure text answer
            if not msg.tool_calls:
                return msg.content or "(Exploration concluded without findings)"

            # Execute tool calls
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                result = self.registry.execute(
                    name=fn_name,
                    arguments=fn_args,
                    ui_approver=self.ui.approve,
                )
                self.ui.tool_execution(fn_name, fn_args, result, is_subagent=True)

                messages.append(
                    Message(
                        role=Role.TOOL,
                        tool_call_id=tool_call.id,
                        content=result,
                    )
                )

        return (
            f"[Exploration completed at max turn limit ({self.max_turns})]\n"
            f"Findings summary:\n{last_known_report or 'No partial report rendered.'}"
        )


class TaskTool(BaseTool):
    """Tool allowing Lead Agent to dispatch the Exploration Subagent."""

    name = "task"
    description = (
        "Dispatch an autonomous read-only Exploration Subagent with its own isolated context window. "
        "Use this for large-scale codebase investigations, tracing data flow, or locating definitions. "
        "The subagent will inspect files and return only a synthesized summary."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Comprehensive, self-contained description of what to discover and where to look.",
            }
        },
        "required": ["description"],
    }

    def __init__(self, agent: ExplorationAgent):
        self.agent = agent

    def run(self, description: str) -> str:
        return self.agent.run(description)
