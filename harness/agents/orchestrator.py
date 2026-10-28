"""Multi-agent orchestrator coordinating Lead, Exploration, Reviewer, and Research agents."""

from typing import Optional
from ..core.config import settings
from ..core.types import Message, Role
from ..mcp.manager import mcp_manager
from ..providers.llm import LLMClient
from ..tools.base import ToolRegistry, registry
from ..tools.browser import BrowserFetchTool, WebSearchTool
from ..tools.code_search import GrepCodeTool, SearchFilesTool
from ..tools.desktop import (
    DesktopScreenshotTool,
    DesktopMouseTool,
    DesktopKeyboardTool,
    DesktopGetWindowsTool,
    DesktopLaunchTool,
)
from ..tools.interactive import AskHumanTool
from ..tools.filesystem import ReadFileTool, StrReplaceTool, WriteFileTool
from ..tools.planner import WriteTodosTool
from ..tools.skills import ReadSkillTool
from ..tools.terminal import BashTool
from ..ui.terminal import TerminalUI, ui
from .base import BaseAgent
from .lead import LeadAgent
from .researcher import ResearchTool, WebResearchAgent
from .reviewer import ReviewerAgent
from .subagent import ExplorationAgent, TaskTool


class AgentOrchestrator:
    """Enterprise multi-agent system builder, tool dependency injector, and MCP connector."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
    ):
        self.llm = llm or LLMClient()
        self.registry = tool_registry or registry
        self.ui = ui_handler or ui

        self._register_default_tools()

        # Connect MCP (Model Context Protocol) external servers if configured
        mcp_manager.load_servers(self.registry)

        from .factory import AgentFactory

        # Instantiate specialized subagents using factory
        self.exploration_subagent = AgentFactory.create_explorer(
            llm=self.llm,
            tool_registry=self.registry,
            ui_handler=self.ui,
        )
        self.registry.register(TaskTool(agent=self.exploration_subagent))

        self.web_research_subagent = AgentFactory.create_researcher(
            llm=self.llm,
            tool_registry=self.registry,
            ui_handler=self.ui,
        )
        self.registry.register(ResearchTool(agent=self.web_research_subagent))

        self.reviewer = AgentFactory.create_reviewer(
            llm=self.llm,
            tool_registry=self.registry,
            ui_handler=self.ui,
        )

        self.lead = AgentFactory.create_lead(
            llm=self.llm,
            tool_registry=self.registry,
            ui_handler=self.ui,
        )

    def _register_default_tools(self):
        """Register core tools with the registry."""
        self.registry.register(ReadFileTool())
        self.registry.register(WriteFileTool())
        self.registry.register(StrReplaceTool())
        self.registry.register(BashTool())
        self.registry.register(SearchFilesTool())
        self.registry.register(GrepCodeTool())
        self.registry.register(ReadSkillTool())
        self.registry.register(WriteTodosTool())
        self.registry.register(BrowserFetchTool())
        self.registry.register(WebSearchTool())
        self.registry.register(AskHumanTool())

        if settings.desktop_enabled:
            self.registry.register(DesktopScreenshotTool())
            self.registry.register(DesktopMouseTool())
            self.registry.register(DesktopKeyboardTool())
            self.registry.register(DesktopGetWindowsTool())
            self.registry.register(DesktopLaunchTool())

        from ..runtime.parallel import DelegateParallelTasksTool
        self.registry.register(DelegateParallelTasksTool())

        from ..tools.qa_tools import (
            RuffLintTool,
            MypyTypeCheckTool,
            PytestRunnerTool,
            SecretScannerTool,
            DependencyAuditTool,
        )
        self.registry.register(RuffLintTool())
        self.registry.register(MypyTypeCheckTool())
        self.registry.register(PytestRunnerTool())
        self.registry.register(SecretScannerTool())
        self.registry.register(DependencyAuditTool())

        from ..tools.searxng import SearXNGSearchTool
        self.registry.register(SearXNGSearchTool())

        from ..tools.browser_automation import SeleniumInspectTool, BrowserUseAgentTool
        self.registry.register(SeleniumInspectTool())
        self.registry.register(BrowserUseAgentTool())

        # Enterprise Memory Architecture Tools: GraphRAG, Reflexion, Long-Term
        from ..memory.graph_memory import QueryCodeGraphTool
        from ..memory.reflexion import RecordLearnedSkillTool
        from ..memory.long_term import RememberFactTool, RecallMemoriesTool
        self.registry.register(QueryCodeGraphTool())
        self.registry.register(RecordLearnedSkillTool())
        self.registry.register(RememberFactTool())
        self.registry.register(RecallMemoriesTool())

    def get_initial_messages(self) -> list[Message]:
        return [Message(role=Role.SYSTEM, content=self.lead.system_prompt)]
