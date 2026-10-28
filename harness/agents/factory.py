from typing import Optional
from ..providers.llm import LLMClient
from ..tools.base import ToolRegistry
from ..ui.terminal import TerminalUI
from .lead import LeadAgent
from .subagent import ExplorationAgent
from .researcher import WebResearchAgent
from .reviewer import ReviewerAgent


class AgentFactory:
    """Factory creating specialized agents with consistent dependencies."""

    @staticmethod
    def create_lead(
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
    ) -> LeadAgent:
        return LeadAgent(llm=llm, tool_registry=tool_registry, ui_handler=ui_handler)

    @staticmethod
    def create_explorer(
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
    ) -> ExplorationAgent:
        return ExplorationAgent(llm=llm, tool_registry=tool_registry, ui_handler=ui_handler)

    @staticmethod
    def create_researcher(
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
    ) -> WebResearchAgent:
        return WebResearchAgent(llm=llm, tool_registry=tool_registry, ui_handler=ui_handler)

    @staticmethod
    def create_reviewer(
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
    ) -> ReviewerAgent:
        return ReviewerAgent(llm=llm, tool_registry=tool_registry, ui_handler=ui_handler)
