"""File System Tools for reading, writing, and exact string replacement."""

from pathlib import Path
from typing import Any, Dict
from ..core.config import settings
from .base import BaseTool


def resolve_path(path_str: str) -> Path:
    """Resolve path. Supports absolute system paths or workspace-relative paths."""
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = settings.workspace_root / p
    return p.resolve()


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read file contents at the given path. Supports optional line slice offset."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file to read"},
            "offset": {"type": "integer", "description": "Optional starting line number (1-indexed)"},
            "limit": {"type": "integer", "description": "Optional maximum number of lines to read"},
        },
        "required": ["path"],
    }

    def run(self, path: str, offset: int = 1, limit: int = 800) -> str:
        resolved = resolve_path(path)
        if not resolved.exists():
            return f"Error: File '{path}' does not exist."
        if resolved.is_dir():
            return f"Error: '{path}' is a directory, not a file."

        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            start_idx = max(0, offset - 1)
            end_idx = min(total_lines, start_idx + limit)

            selected_lines = lines[start_idx:end_idx]
            result = []
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                result.append(f"{i:>5} | {line}")

            header = f"=== File: {path} (Lines {start_idx + 1}-{end_idx} of {total_lines}) ===\n"
            return header + "".join(result)
        except Exception as e:
            return f"Error reading file '{path}': {str(e)}"


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Create a file or overwrite it completely with new content."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path of file to write"},
            "content": {"type": "string", "description": "The exact full text content to write"},
        },
        "required": ["path", "content"],
    }

    def run(self, path: str, content: str) -> str:
        resolved = resolve_path(path)
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to '{path}'."
        except Exception as e:
            return f"Error writing file '{path}': {str(e)}"


class StrReplaceTool(BaseTool):
    name = "str_replace"
    description = (
        "Replace exact text in a file. 'old_str' must appear uniquely, or set allow_multi_edit=True. "
        "Include surrounding lines if necessary to ensure uniqueness."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file to edit"},
            "old_str": {"type": "string", "description": "Exact substring to find and replace"},
            "new_str": {"type": "string", "description": "Replacement text"},
            "allow_multi_edit": {"type": "boolean", "description": "Allow replacing multiple occurrences"},
        },
        "required": ["path", "old_str", "new_str"],
    }

    def run(self, path: str, old_str: str, new_str: str, allow_multi_edit: bool = False) -> str:
        resolved = resolve_path(path)
        if not resolved.exists():
            return f"Error: File '{path}' does not exist."

        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            count = content.count(old_str)
            if count == 0:
                return f"Error: old_str was not found in '{path}'."
            if count > 1 and not allow_multi_edit:
                return (
                    f"Error: old_str matched {count} times in '{path}'. "
                    "Include additional surrounding context lines to make the match unique, "
                    "or set allow_multi_edit=true."
                )

            updated = content.replace(old_str, new_str)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(updated)

            return f"Successfully replaced {count} occurrence(s) in '{path}'."
        except Exception as e:
            return f"Error editing file '{path}': {str(e)}"
