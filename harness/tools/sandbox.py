"""Sandboxed Execution Environment for shell commands and system tools."""

import subprocess
import os
import sys
from pathlib import Path
from typing import Tuple
from ..core.config import settings


class Sandbox:
    """Safe execution environment isolating working directory and enforcing timeouts."""

    def __init__(self, root_dir: Path = None, timeout: int = None):
        self.root_dir = (root_dir or settings.workspace_root).resolve()
        self.timeout = timeout or settings.tool_timeout_seconds

    def name(self) -> str:
        return self.root_dir.name

    def run(self, command: str) -> Tuple[int, str, str]:
        """Execute command in sandbox directory with timeout.
        
        Returns:
            (exit_code, stdout, stderr)
        """
        # Determine appropriate shell based on OS
        is_windows = sys.platform.startswith("win")
        
        try:
            process = subprocess.run(
                command,
                shell=True,
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PAGER": "cat", "GIT_PAGER": "cat"},
            )
            return process.returncode, process.stdout, process.stderr
        except subprocess.TimeoutExpired as expired:
            return -1, "", f"Execution timed out after {expired.timeout}s and was terminated."
        except Exception as e:
            return 1, "", f"Failed to execute command '{command}': {str(e)}"


# Default sandbox instance
default_sandbox = Sandbox()
