"""Self-Reflective / Procedural Memory (Reflexion Engine).

When an agent encounters a broken build, failing test, or command failure
and subsequently resolves it, Reflexion automatically synthesizes:
1. Root cause & symptoms
2. The exact successful resolution
3. Generates a permanent, reusable SKILL.md playbook in .agents/skills/
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..core.config import settings
from ..tools.base import BaseTool

logger = logging.getLogger(__name__)

SKILL_TEMPLATE = """---
name: {skill_name}
description: {description}
---

# {title}

## Problem & Error Symptoms
{symptoms}

## Root Cause
{root_cause}

## Verified Resolution & Playbook
{playbook}

*Generated automatically by Reflexion Procedural Memory on {timestamp}*
"""


class ReflexionEngine:
    """Detects failure-then-success sequences and synthesizes procedural playbooks."""

    def __init__(self, skills_dir: Optional[Path] = None):
        base = skills_dir or (settings.workspace_root / ".agents" / "skills")
        self.skills_dir = base
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._failure_trail: List[Dict[str, Any]] = []

    def record_failure(self, action: str, error_message: str):
        """Record an attempted command/test/tool failure."""
        self._failure_trail.append({
            "action": action,
            "error": error_message[:500],
            "timestamp": datetime.now().isoformat(),
        })

    def record_success_and_reflect(self, action: str, resolution_notes: str) -> Optional[str]:
        """If there was a prior recorded failure, synthesize into a reusable skill."""
        if not self._failure_trail:
            return None

        recent_failure = self._failure_trail[-1]
        self._failure_trail.clear()

        # Sanitize skill name
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", action).strip("_").lower()[:30]
        skill_name = f"fix_{slug}"

        target_dir = self.skills_dir / skill_name
        target_dir.mkdir(parents=True, exist_ok=True)
        skill_file = target_dir / "SKILL.md"

        content = SKILL_TEMPLATE.format(
            skill_name=skill_name,
            description=f"Auto-learned playbook for resolving errors in {action}",
            title=f"Resolution Playbook: {action}",
            symptoms=recent_failure.get("error", "Command or test failed with non-zero exit code."),
            root_cause="Identified and corrected during autonomous execution.",
            playbook=resolution_notes,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        skill_file.write_text(content, encoding="utf-8")
        logger.info(f"Reflexion generated new skill playbook: {skill_file}")
        return str(skill_file)

    def learn_manual_lesson(self, title: str, symptoms: str, resolution: str) -> str:
        """Explicitly author a procedural skill."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower()[:30]
        skill_name = f"skill_{slug}"

        target_dir = self.skills_dir / skill_name
        target_dir.mkdir(parents=True, exist_ok=True)
        skill_file = target_dir / "SKILL.md"

        content = SKILL_TEMPLATE.format(
            skill_name=skill_name,
            description=f"Reusable playbook: {title}",
            title=title,
            symptoms=symptoms,
            root_cause="Observed during development.",
            playbook=resolution,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        skill_file.write_text(content, encoding="utf-8")
        return str(skill_file)


default_reflexion = ReflexionEngine()


class RecordLearnedSkillTool(BaseTool):
    """Tool enabling the agent to manually synthesize a learned lesson into a permanent Skill."""

    name = "record_learned_skill"
    description = (
        "Record a verified bug fix, setup procedure, or architectural lesson into the persistent Skill Library. "
        "Creates a reusable playbook in .agents/skills/ so future sessions and subagents never repeat the same error."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title describing the problem and solution (e.g. 'Fixing Windows Wintun driver linking').",
            },
            "symptoms": {
                "type": "string",
                "description": "Error trace, failure conditions, or unexpected behavior observed.",
            },
            "resolution": {
                "type": "string",
                "description": "Step-by-step verified instructions, code diff, or configuration to fix it.",
            },
        },
        "required": ["title", "resolution"],
    }

    def __init__(self, reflexion: Optional[ReflexionEngine] = None):
        self.reflexion = reflexion or default_reflexion

    def run(self, title: str, resolution: str, symptoms: str = "Command failed") -> str:
        saved_path = self.reflexion.learn_manual_lesson(title=title, symptoms=symptoms, resolution=resolution)
        from ..tools.skills import skill_manager
        skill_manager.refresh()
        return f"Successfully crystallized procedural skill to: {saved_path}. Now available across all runs via 'read_skill'."

