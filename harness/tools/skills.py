"""Skill discovery and loading tools."""

from pathlib import Path
from typing import Dict
import yaml
from ..core.config import settings
from .base import BaseTool


class SkillManager:
    """Discovers, indexes, and loads custom skill playbooks from .agents/skills."""

    def __init__(self):
        self.search_dirs = [
            settings.workspace_root / ".agents" / "skills",
            Path.home() / ".agents" / "skills",
        ]
        self._cache: Dict[str, Dict[str, str]] = {}
        self.refresh()

    def refresh(self):
        self._cache.clear()
        for directory in self.search_dirs:
            if not directory.exists():
                continue
            for skill_file in sorted(directory.glob("*/SKILL.md")):
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        _, frontmatter, body = content.split("---", 2)
                        meta = yaml.safe_load(frontmatter) or {}
                        name = meta.get("name", skill_file.parent.name)
                        desc = meta.get("description", "No description provided.")
                        self._cache[name] = {
                            "description": desc.strip(),
                            "path": str(skill_file),
                            "body": body.strip(),
                        }
                except Exception:
                    continue

    def list_skills(self) -> Dict[str, str]:
        return {name: info["description"] for name, info in self._cache.items()}

    def get_skill_content(self, name: str) -> str:
        if name not in self._cache:
            self.refresh()
        if name not in self._cache:
            return f"Error: No skill named '{name}' found."
        return Path(self._cache[name]["path"]).read_text(encoding="utf-8")


skill_manager = SkillManager()


class ReadSkillTool(BaseTool):
    name = "read_skill"
    description = "Read full instructional guide and workflow for an active skill playbook."
    parameters_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The exact name of the skill to read"},
        },
        "required": ["name"],
    }

    def run(self, name: str) -> str:
        return skill_manager.get_skill_content(name)
