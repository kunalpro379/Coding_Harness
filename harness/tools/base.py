"""Abstract Base Tool and Tool Registry for extensible tool definitions."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel
from .permissions import default_policy


class BaseTool(ABC):
    """Abstract base class for all tools in the coding harness."""

    name: str
    description: str
    parameters_schema: Dict[str, Any]

    @abstractmethod
    def run(self, **kwargs) -> str:
        """Execute the tool with keyword arguments and return string output."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Convert into OpenAI function calling schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class ToolRegistry:
    """Registry managing available tools and schema generation."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> BaseTool:
        """Register a tool instance."""
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_schemas(self, exclude: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        exclude = set(exclude or [])
        return [
            tool.get_schema()
            for name, tool in self._tools.items()
            if name not in exclude
        ]

    def execute(self, name: str, arguments: Dict[str, Any], ui_approver: Optional[Callable[[str], bool]] = None) -> str:
        """Execute a tool with policy checks, safety guards, and error captures."""
        if name not in self._tools:
            available = ", ".join(self._tools.keys())
            return f"Error: Tool '{name}' not found. Available tools: {available}"

        # Run policy check
        action, reason = default_policy.evaluate(name, arguments)
        if action == "deny":
            return f"Error: Tool call blocked by security policy - {reason}"
        if action == "ask":
            approved = ui_approver(reason) if ui_approver else True
            if not approved:
                return "Error: User denied permission to execute tool."

        tool = self._tools[name]
        try:
            return tool.run(**arguments)
        except TypeError as te:
            return f"Error: Invalid arguments provided to {name}: {te}"
        except Exception as e:
            return f"Error: Execution of {name} failed ({type(e).__name__}): {str(e)}"


registry = ToolRegistry()
