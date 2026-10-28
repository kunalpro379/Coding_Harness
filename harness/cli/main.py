"""Interactive Command Line Interface for the Coding Harness."""

import sys
from typing import Optional
import typer
from rich.prompt import Prompt

from ..agents.orchestrator import AgentOrchestrator
from ..core.config import settings
from ..memory.session import session_manager
from ..memory.trimmer import trimmer
from ..ui.commands import command_handler
from ..ui.terminal import ui

app = typer.Typer(help="Cursor Agent: Production Multi-Agent Coding Harness")


@app.command()
def main(
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume latest previous session"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Print debug diagnostics"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override default LLM model"),
    no_sandbox: bool = typer.Option(False, "--no-sandbox", help="Run without sandbox restrictions; allow system-wide access"),
):
    """Start the Cursor Agent harness interactive session."""
    if model:
        settings.model = model
    if no_sandbox:
        settings.no_sandbox = True
        ui.warning("Running in --no-sandbox mode: full system access is permitted.")

    orchestrator = AgentOrchestrator()
    ui.banner(project_name=orchestrator.lead.name, model_name=settings.model)

    messages = orchestrator.get_initial_messages()

    if resume:
        saved = session_manager.list_sessions()
        if saved:
            latest_id = saved[0]["id"]
            messages = session_manager.load_session(latest_id)
            trimmer.strip_turn(messages)
            ui.success(f"Resumed previous session: {latest_id} ({len(messages)} messages loaded).")
        else:
            ui.note("No previous sessions found to resume. Starting fresh session.")

    while True:
        try:
            user_input = ui.ask()
            if not user_input:
                continue

            # Check for interactive slash command
            if user_input.startswith("/"):
                messages, should_save = command_handler.handle(user_input, messages)
                if should_save:
                    session_manager.save(messages)
                continue

            # Run agent turn
            messages = orchestrator.lead.run_turn(
                user_input=user_input,
                messages=messages,
                debug=debug,
            )

        except (KeyboardInterrupt, EOFError):
            ui.note("\nExiting session. Transcript saved.")
            break
        except Exception as e:
            ui.error(f"Unexpected error occurred: {e}")
            if debug:
                import traceback
                traceback.print_exc()


def run_cli():
    app()


if __name__ == "__main__":
    run_cli()
