from pathlib import Path
from .base import BaseTool
from .sandbox import Sandbox, default_sandbox


class BashTool(BaseTool):
    name = "bash"
    description = (
        "Run a shell command on the system and return its combined stdout and stderr. "
        "Can execute within any directory (cwd) or system-wide."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command line string to run"},
            "cwd": {"type": "string", "description": "Optional working directory path (defaults to workspace or current dir)"},
            "timeout": {"type": "integer", "description": "Optional execution timeout in seconds"},
        },
        "required": ["command"],
    }

    def __init__(self, sandbox=None):
        self.sandbox = sandbox or default_sandbox

    def run(self, command: str, cwd: str = None, timeout: int = None) -> str:
        sandbox = self.sandbox
        effective_root = sandbox.root_dir
        if cwd:
            c_path = Path(cwd).expanduser()
            if not c_path.is_absolute():
                effective_root = (sandbox.root_dir / c_path).resolve()
            else:
                effective_root = c_path.resolve()

        effective_timeout = sandbox.timeout
        if timeout is not None:
            try:
                effective_timeout = int(timeout)
            except (ValueError, TypeError):
                pass

        runner = Sandbox(root_dir=effective_root, timeout=effective_timeout)
        code, stdout, stderr = runner.run(command)
        out = (stdout + stderr).strip()
        if not out:
            return f"(Command executed with exit code {code}, produced no output)"
        if code != 0:
            return f"[Process exited with code {code}]\n{out}"
        return out
