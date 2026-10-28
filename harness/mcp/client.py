import asyncio
import json
import logging
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class MCPToolDefinition(BaseModel):
    """Schema representing an MCP tool definition advertised by a server."""
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class MCPTransport(ABC):
    """Abstract interface for communicating with an MCP server."""

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def close(self):
        pass


class StdioMCPTransport(MCPTransport):
    def __init__(self, command: str, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args or []
        self.env = env
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0

    def connect(self):
        cmd = [self.command] + self.args
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=self.env,
                bufsize=1,
            )
        except Exception as e:
            logger.warning(f"Failed to spawn MCP server {cmd}: {e}")
            self.process = None

    def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.process or self.process.poll() is not None:
            self.connect()

        if not self.process or not self.process.stdin:
            return {"error": "MCP server process not running."}

        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        try:
            raw_msg = json.dumps(payload) + "\n"
            self.process.stdin.write(raw_msg)
            self.process.stdin.flush()

            # Read single response line
            line = self.process.stdout.readline()
            if not line:
                return {"error": "Server returned empty response or process exited."}
            return json.loads(line)
        except Exception as e:
            logger.error(f"MCP stdio transport error: {e}")
            return {"error": str(e)}

    def close(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
            self.process = None
class MCPClient:
    """High-level Client managing MCP protocol lifecycle and tool enumeration."""

    def __init__(self, server_name: str, transport: MCPTransport):
        self.server_name = server_name
        self.transport = transport
        self._tools: List[MCPToolDefinition] = []

    def initialize(self) -> bool:
        """Handshake with the server according to MCP specification."""
        try:
            self.transport.connect()
            resp = self.transport.send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "cursor-agent-harness", "version": "1.0.0"},
                },
            )
            if "error" in resp:
                logger.warning(f"MCP server '{self.server_name}' initialize failed: {resp['error']}")
                return False

            self.transport.send_request("notifications/initialized")
            self.fetch_tools()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize MCP client '{self.server_name}': {e}")
            return False

    def fetch_tools(self) -> List[MCPToolDefinition]:
        """Query available tools from server."""
        resp = self.transport.send_request("tools/list")
        tools_data = resp.get("result", {}).get("tools", [])
        self._tools = [
            MCPToolDefinition(
                name=t.get("name"),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools_data
        ]
        return self._tools

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Invoke a tool on the remote MCP server."""
        resp = self.transport.send_request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        if "error" in resp:
            return f"MCP Error ({self.server_name}): {resp['error']}"

        result = resp.get("result", {})
        content_items = result.get("content", [])
        text_parts = [c.get("text", "") for c in content_items if c.get("type") == "text"]
        return "\n".join(text_parts) if text_parts else str(result)

    def close(self):
        self.transport.close()
