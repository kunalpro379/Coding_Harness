"""MCP Server Registry and Dynamic Tool Adapter."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from ..core.config import settings
from ..tools.base import BaseTool, ToolRegistry
from .client import MCPClient, StdioMCPTransport


class MCPToolAdapter(BaseTool):
    """Adapts an MCP-provided tool to the harness BaseTool interface."""

    def __init__(self, client: MCPClient, mcp_name: str, description: str, schema: dict):
        self.client = client
        self.name = f"mcp_{client.server_name}_{mcp_name}"
        self.description = f"[MCP Server: {client.server_name}] {description}"
        self.parameters_schema = schema
        self._target_mcp_name = mcp_name

    def run(self, **kwargs) -> str:
        return self.client.call_tool(self._target_mcp_name, kwargs)


class MCPManager:
    """Discovers MCP configurations (e.g. from mcp_config.json) and registers tools."""

    def __init__(self, config_paths: Optional[List[Path]] = None):
        self.config_paths = config_paths or [
            settings.workspace_root / "mcp_config.json",
            Path.home() / ".gemini" / "antigravity-ide" / "mcp_config.json",
            Path.home() / ".agents" / "mcp.json",
        ]
        self.clients: Dict[str, MCPClient] = {}

    def load_servers(self, tool_registry: ToolRegistry):
        """Read configuration files and instantiate MCP clients and adapters."""
        for path in self.config_paths:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                mcp_servers = data.get("mcpServers", {})
                for name, conf in mcp_servers.items():
                    if name in self.clients:
                        continue
                    cmd = conf.get("command")
                    args = conf.get("args", [])
                    env = conf.get("env")
                    if not cmd:
                        continue

                    transport = StdioMCPTransport(command=cmd, args=args, env=env)
                    client = MCPClient(server_name=name, transport=transport)
                    if client.initialize():
                        self.clients[name] = client
                        for tool_def in client.fetch_tools():
                            adapter = MCPToolAdapter(
                                client=client,
                                mcp_name=tool_def.name,
                                description=tool_def.description,
                                schema=tool_def.input_schema,
                            )
                            tool_registry.register(adapter)
            except Exception:
                continue

    def shutdown(self):
        for client in self.clients.values():
            client.close()
        self.clients.clear()


mcp_manager = MCPManager()
