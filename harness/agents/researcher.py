"""Specialized Web Research Subagent.

Runs in an isolated ephemeral context to query search engines, crawl documentation,
and extract exact technical APIs without polluting the Lead Agent's coding transcript.
"""

from typing import Optional
from ..core.types import Message, Role
from ..providers.llm import LLMClient
from ..tools.base import BaseTool, ToolRegistry
from ..ui.terminal import TerminalUI
from .base import BaseAgent

RESEARCH_PROMPT = """
You are a Web Research Subagent.
A Lead Architect requested documentation or solutions for an external library, framework, or bug.
Your mission is to use web_search and browser_fetch to locate verified documentation and APIs.

Guidelines:
1. Formulate precise queries.
2. Fetch authoritative documentation pages.
3. Return only synthesized, concrete code snippets, parameters, and signatures.
4. Keep the final report under 250 words.
"""


class WebResearchAgent(BaseAgent):
    """Subagent specialized in external research and documentation parsing."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
        max_turns: int = 8,
    ):
        super().__init__(
            name="WebResearchAgent",
            role_description="External documentation detective",
            system_prompt=RESEARCH_PROMPT,
            llm=llm,
            tool_registry=tool_registry,
            ui_handler=ui_handler,
        )
        self.max_turns = max_turns

    def run(self, topic: str) -> str:
        messages = [
            Message(role=Role.SYSTEM, content=self.system_prompt),
            Message(role=Role.USER, content=f"Research documentation and solution for: {topic}"),
        ]
        tools_schemas = self.registry.get_schemas(exclude=["write_file", "str_replace", "write_todos", "task"])

        last_report = None
        for _ in range(self.max_turns):
            with self.ui.spinner("Web research subagent querying documentation..."):
                resp = self.llm.complete(messages, tools=tools_schemas)

            msg = resp.message
            messages.append(msg)
            if msg.content:
                last_report = msg.content

            if not msg.tool_calls:
                return msg.content or "Research completed without findings."

            for tc in msg.tool_calls:
                import json
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                res = self.registry.execute(tc.function.name, args, self.ui.approve)
                self.ui.tool_execution(tc.function.name, args, res, is_subagent=True)
                messages.append(Message(role=Role.TOOL, tool_call_id=tc.id, content=res))

        return last_report or "Research stopped after max turns."


class ResearchTool(BaseTool):
    """Tool allowing Lead Agent to dispatch the WebResearchAgent."""

    name = "research"
    description = (
        "Dispatch a Web Research Subagent to search online documentation, look up error messages, "
        "or read external API references. Runs in its own context window and returns only the final summary."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "The specific technical question or library to research"},
        },
        "required": ["topic"],
    }

    def __init__(self, agent: WebResearchAgent):
        self.agent = agent

    def run(self, topic: str) -> str:
        return self.agent.run(topic)
