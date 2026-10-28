"""Semantic code and file search tools."""

import fnmatch
import os
import re
from pathlib import Path
from typing import List
from ..core.config import settings
from .base import BaseTool


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Search for files and directories matching a glob pattern (e.g. '*.py', '**/tests/*.ts')."
    parameters_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern to match file names (e.g. '*.py', '*.txt')"},
            "directory": {"type": "string", "description": "Directory to search from (relative to workspace or absolute path)"},
            "max_results": {"type": "integer", "description": "Maximum number of files to return (default 50)"},
        },
        "required": ["pattern"],
    }

    def run(self, pattern: str, directory: str = ".", max_results: int = 50) -> str:
        d_path = Path(directory).expanduser()
        if not d_path.is_absolute():
            root = (settings.workspace_root / d_path).resolve()
        else:
            root = d_path.resolve()

        if not root.exists():
            return f"Error: Search directory '{directory}' does not exist."

        matches = []
        try:
            for path in root.rglob(pattern):
                # Ignore common bloated directories
                parts = path.parts
                if any(p in {".git", "__pycache__", "node_modules", ".venv", "dist", "build"} for p in parts):
                    continue
                try:
                    rel = str(path.relative_to(settings.workspace_root))
                except ValueError:
                    rel = str(path)
                matches.append(rel)
                if len(matches) >= max_results:
                    break
        except Exception as e:
            return f"Error searching files: {e}"

        if not matches:
            return f"No files matched pattern '{pattern}' in '{directory}'."
        return "\n".join(matches)


class GrepCodeTool(BaseTool):
    name = "grep_code"
    description = "Search for a regex or substring pattern across all files in the workspace."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Regex or text string to search for"},
            "path": {"type": "string", "description": "Directory or file to search in (defaults to workspace root)"},
            "is_regex": {"type": "boolean", "description": "Whether query is a regex pattern (default false)"},
            "max_results": {"type": "integer", "description": "Max matching lines to return (default 50)"},
        },
        "required": ["query"],
    }

    def run(self, query: str, path: str = ".", is_regex: bool = False, max_results: int = 50) -> str:
        p_obj = Path(path).expanduser()
        if not p_obj.is_absolute():
            root = (settings.workspace_root / p_obj).resolve()
        else:
            root = p_obj.resolve()

        if not root.exists():
            return f"Error: Path '{path}' does not exist."

        flags = re.IGNORECASE
        try:
            pattern = re.compile(query if is_regex else re.escape(query), flags)
        except re.error as e:
            return f"Error: Invalid regular expression '{query}': {e}"

        results = []
        files_to_check = [root] if root.is_file() else root.rglob("*")

        for file_path in files_to_check:
            if not file_path.is_file():
                continue
            if any(p in {".git", "__pycache__", "node_modules", ".venv", "dist", "build"} for p in file_path.parts):
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        if pattern.search(line):
                            try:
                                disp_path = str(file_path.relative_to(settings.workspace_root))
                            except ValueError:
                                disp_path = str(file_path)
                            results.append(f"{disp_path}:{line_num}: {line.strip()[:150]}")
                            if len(results) >= max_results:
                                return "\n".join(results)
            except Exception:
                continue

        if not results:
            return f"No matches found for '{query}' in '{path}'."
        return "\n".join(results)
