"""Base abstract class for all autonomous agent implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from ..core.types import LLMResponse, Message, Role, TokenUsage
from ..providers.llm import LLMClient, default_llm
from ..tools.base import ToolRegistry, registry
from ..ui.terminal import TerminalUI, ui


class BaseAgent(ABC):
    """Abstract base agent providing prompt generation, execution loop, and tool handling."""

    def __init__(
        self,
        name: str,
        role_description: str,
        system_prompt: str,
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
    ):
        self.name = name
        self.role_description = role_description
        self.system_prompt = system_prompt
        self.llm = llm or default_llm
        self.registry = tool_registry or registry
        self.ui = ui_handler or ui

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Core execution logic."""
        pass
