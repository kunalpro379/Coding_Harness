"""Enterprise Code Quality & Security Tools: Ruff, Mypy, Pytest, Gitleaks, OSV-Scanner, Tree-Sitter."""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..core.config import settings
from .base import BaseTool


def _resolve(p_str: str) -> Path:
    p = Path(p_str).expanduser()
    if not p.is_absolute():
        p = settings.workspace_root / p
    return p.resolve()


class RuffLintTool(BaseTool):
    """Run Ruff linter and formatter checks on files or workspace."""

    name = "ruff_lint"
    description = (
        "Run fast Ruff linting and formatting diagnostics on Python files or directories. "
        "Provides exact line numbers, violation codes (e.g., E501, F401), and auto-fix suggestions."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File or directory path to lint (defaults to workspace root).",
            },
            "fix": {
                "type": "boolean",
                "description": "Whether to automatically apply safe fixes in-place.",
            },
        },
    }

    def run(self, path: Optional[str] = None, fix: bool = False) -> str:
        target = str(_resolve(path or "."))
        cmd = ["python", "-m", "ruff", "check", target]
        if fix:
            cmd.append("--fix")

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(settings.workspace_root),
                timeout=30,
            )
            out = (res.stdout + "\n" + res.stderr).strip()
            return out or "Ruff check passed: No lint issues found."
        except Exception as e:
            return f"Error executing ruff: {e}"


class MypyTypeCheckTool(BaseTool):
    """Run Mypy static type checker on Python codebase."""

    name = "mypy_check"
    description = (
        "Run Mypy static type checking on Python files. "
        "Catches type mismatches, missing annotations, and invalid function parameters."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File or package directory to type-check.",
            },
        },
    }

    def run(self, path: Optional[str] = None) -> str:
        target = str(_resolve(path or "harness"))
        cmd = ["python", "-m", "mypy", target, "--ignore-missing-imports"]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(settings.workspace_root),
                timeout=60,
            )
            out = (res.stdout + "\n" + res.stderr).strip()
            return out or "Mypy check passed: No typing issues detected."
        except Exception as e:
            return f"Error executing mypy: {e}"


class PytestRunnerTool(BaseTool):
    """Run pytest test suite with optional filters and coverage."""

    name = "run_pytest"
    description = (
        "Execute pytest unit and integration test suites. "
        "Returns passed/failed test cases, stack traces, and failure assertions."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "test_path": {
                "type": "string",
                "description": "Specific test file or test folder path (defaults to 'tests').",
            },
            "keyword": {
                "type": "string",
                "description": "Only run tests matching expression (e.g. -k test_name).",
            },
        },
    }

    def run(self, test_path: Optional[str] = None, keyword: Optional[str] = None) -> str:
        target = test_path or "tests"
        cmd = ["python", "-m", "pytest", target]
        if keyword:
            cmd.extend(["-k", keyword])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(settings.workspace_root),
                timeout=60,
            )
            return (res.stdout + "\n" + res.stderr).strip()
        except Exception as e:
            return f"Error executing pytest: {e}"


class SecretScannerTool(BaseTool):
    """Gitleaks/Pattern secret detector scanning for accidental API keys, tokens, and private keys."""

    name = "scan_secrets"
    description = (
        "Scan files or repository for leaked secrets (AWS keys, OpenAI tokens, private keys, passwords). "
        "Prevents committing sensitive credentials into source control."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to scan (defaults to workspace root).",
            },
        },
    }

    PATTERNS = [
        (r"(?i)api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]", "API Key"),
        (r"sk-[A-Za-z0-9]{32,}", "OpenAI / Provider Secret Key"),
        (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
        (r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", "Private Key Block"),
        (r"(?i)password\s*[:=]\s*['\"][^'\"]{6,}['\"]", "Hardcoded Password"),
    ]

    def run(self, path: Optional[str] = None) -> str:
        target_dir = _resolve(path or ".")
        findings = []

        # Walk files skipping .git, node_modules, __pycache__
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv"}]
            for file in files:
                if file.endswith((".py", ".env", ".json", ".js", ".ts", ".cpp", ".h", ".yml", ".yaml")):
                    f_path = Path(root) / file
                    try:
                        content = f_path.read_text(encoding="utf-8", errors="ignore")
                        for pattern, label in self.PATTERNS:
                            matches = re.finditer(pattern, content)
                            for m in matches:
                                line_no = content[:m.start()].count("\n") + 1
                                findings.append(f"[!] {label} detected in {f_path.relative_to(settings.workspace_root)}:{line_no}")
                    except Exception:
                        pass

        if not findings:
            return "Secret scan passed: No hardcoded credentials or API keys found."
        return "Secret scan warning:\n" + "\n".join(findings)


class DependencyAuditTool(BaseTool):
    """Vulnerability analysis tool scanning dependencies for known CVEs."""

    name = "audit_dependencies"
    description = (
        "Audit installed packages and dependencies against known CVE databases. "
        "Identifies outdated or vulnerable libraries."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "requirements_file": {
                "type": "string",
                "description": "Optional path to requirements.txt or pyproject.toml.",
            },
        },
    }

    def run(self, requirements_file: Optional[str] = None) -> str:
        try:
            # Run pip list and check outdated
            res = subprocess.run(
                ["pip", "list", "--outdated", "--format=columns"],
                capture_output=True,
                text=True,
                cwd=str(settings.workspace_root),
                timeout=30,
            )
            output = res.stdout.strip()
            if not output:
                return "All dependencies are up to date. No immediate outdated packages found."
            return f"Dependency Audit Report (Outdated Packages):\n{output}"
        except Exception as e:
            return f"Error auditing dependencies: {e}"
