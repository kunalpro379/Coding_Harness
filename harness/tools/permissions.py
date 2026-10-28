"""Security & Permission Controller for tool executions.

Inspects tool calls against policy:
- allow: execute transparently
- ask: request explicit user approval
- deny: reject immediately
"""

from typing import Any, Dict, Tuple
from ..core.config import settings

READONLY_TOOLS = {"read_file", "search_files", "grep_code", "list_dir", "read_skill", "desktop_screenshot", "desktop_get_windows", "ask_human"}
DANGEROUS_PATTERNS = ["rm -rf", "drop database", "format ", "mkfs", ":(){ :|:& };:"]
CRITICAL_PATHS = ["C:\\Windows", "C:\\Program Files", "System32", ".ssh", "id_rsa"]


class SecurityPolicy:
    """Evaluates whether an action is safe or requires human authorization."""

    def __init__(self, auto_approve_read: bool = True, require_approval: bool = False, no_sandbox: bool = False):
        self.auto_approve_read = auto_approve_read
        self.require_approval = require_approval
        self.no_sandbox = no_sandbox

    def evaluate(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[str, str]:
        """Returns (action, reason) where action is 'allow', 'ask', or 'deny'."""
        if tool_name in READONLY_TOOLS:
            return "allow", "Read-only or human-interaction operation permitted."

        # High-risk bash operations require human confirmation even in no_sandbox
        if tool_name == "bash":
            cmd = arguments.get("command", "").strip()
            for dangerous in DANGEROUS_PATTERNS:
                if dangerous in cmd:
                    return "ask", f"High-risk command detected ('{dangerous}'): human confirmation required."

            # If user enabled strict approval
            if self.require_approval:
                return "ask", f"Command requires confirmation: '{cmd}'"

            return "allow", "Shell command approved."

        if tool_name in {"write_file", "str_replace"}:
            path = arguments.get("path", "")
            for crit in CRITICAL_PATHS:
                if crit.lower() in path.lower():
                    return "ask", f"Modifying sensitive system or credential path: '{path}'"
            if not self.no_sandbox and (".git/" in path or ".env" in path):
                return "ask", f"Modifying sensitive project configuration: '{path}'"
            return "allow", f"File edit allowed for '{path}'."

        if self.no_sandbox:
            return "allow", "Running in no-sandbox mode: action allowed."

        return "allow", "Default tool policy allowed."


default_policy = SecurityPolicy(
    auto_approve_read=settings.auto_approve_readonly,
    require_approval=settings.require_approval_commands,
    no_sandbox=settings.no_sandbox,
)
