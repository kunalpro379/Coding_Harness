"""Human-in-the-Loop interactive tools.

Empowers autonomous agents to solicit human input, clarify ambiguities,
request confirmation for sensitive actions, and choose from alternatives.
"""

from typing import List, Optional
from .base import BaseTool
from ..ui.terminal import ui


class AskHumanTool(BaseTool):
    """Tool allowing the agent to ask the human user a clarifying question or request instructions."""

    name = "ask_human"
    description = (
        "Ask the human user a question, clarify underspecified requirements, request credentials/keys, "
        "or ask how to proceed when facing multiple technical design choices or ambiguous errors."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The clear question or prompt for the user"},
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of predefined choices for the user to select from",
            },
        },
        "required": ["question"],
    }

    def run(self, question: str, options: Optional[List[str]] = None) -> str:
        ui.console.print()
        ui.console.print(f"[bold yellow][Human-in-the-Loop Intervention Requested][/bold yellow]")
        ui.console.print(f"[bold cyan]{question}[/bold cyan]")

        if options and len(options) > 0:
            idx = ui.pick(question, options)
            if idx is not None:
                selected = options[idx]
                ui.success(f"Human selected: {selected}")
                return f"Human response: Option #{idx + 1} - '{selected}'"
            ui.note("No option chosen by index, prompting for text input...")

        response = ui.ask(prompt="Your answer> ")
        if not response:
            return "Human gave empty response (skipped/cancelled)."
        ui.success(f"Human responded: {response}")
        return f"Human response: {response}"
