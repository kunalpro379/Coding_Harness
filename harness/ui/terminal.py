"""Interactive terminal UI powered by Rich."""

from typing import Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.status import Status
from rich.syntax import Syntax


"""Interactive terminal UI powered by Rich."""

import re
from typing import Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.status import Status
from rich.syntax import Syntax


class TerminalUI:
    """Production console interface rendering styling, tables, tool previews, and diffs."""

    def __init__(self):
        self.console = Console()

    def banner(self, project_name: str, model_name: str):
        self.console.print()
        self.console.print(f"* CURSOR AGENT HARNESS [{project_name}] Model: {model_name}")
        self.console.print("Type your prompt, or use slash commands (/rewind, /sessions, /compact, /plan, /help)\n")

    def note(self, message: str, style: str = "white"):
        self.console.print(f"[INFO] {message}")

    def warning(self, message: str):
        self.console.print(f"[WARN] {message}")

    def error(self, message: str):
        self.console.print(f"[ERROR] {message}")

    def success(self, message: str):
        self.console.print(f"[OK] {message}")

    def ask(self, prompt: str = "agent> ") -> str:
        self.console.print()
        try:
            return self.console.input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            return ""

    def approve(self, reason: str) -> bool:
        self.console.print(f"\n[SECURITY APPROVAL REQUIRED] {reason}")
        try:
            choice = self.console.input("Allow this action? (y/N): ").strip().lower()
            return choice in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False

    def display_step(self, step_number: int):
        self.console.print(f"\n=== Step {step_number} ===")

    def display_thinking(self, thought: str):
        if not thought.strip():
            return
        self.console.print("[Thinking]")
        self.console.print(f"{thought.strip()}\n")

    def assistant_message(self, content: str):
        if not content:
            return
        
        # Check for <thought>...</thought> tags in model output
        thought_match = re.search(r"<thought>(.*?)</thought>", content, flags=re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
            self.display_thinking(thought)
            # Remove <thought> block from user-facing message
            content = re.sub(r"<thought>.*?</thought>", "", content, flags=re.DOTALL).strip()

        if content:
            self.console.print()
            self.console.print(content)

    def tool_execution(self, name: str, args: dict, result: str, is_subagent: bool = False):
        prefix = "  [subagent] " if is_subagent else ">> "
        preview = str(args)[:100] + ("..." if len(str(args)) > 100 else "")
        self.console.print(f"{prefix}{name} ({preview})")
        
        # Tool output: plain and minimal dull gray
        if len(result) > 400:
            preview_res = result[:400] + f"\n... [+{len(result)-400} chars]"
            self.console.print(f"[grey50]{preview_res}[/grey50]")
        elif result.strip():
            self.console.print(f"[grey50]{result.strip()}[/grey50]")

    def display_usage(self, usage: Any):
        prompt = getattr(usage, "prompt_tokens", 0)
        completion = getattr(usage, "completion_tokens", 0)
        total = getattr(usage, "total_tokens", prompt + completion)
        cached = getattr(usage, "cached_tokens", 0) or 0
        self.console.print(
            f"Tokens: total={total:,} (prompt={prompt:,}, completion={completion:,}, cached={cached:,})"
        )

    def display_plan(self, todos_text: str):
        if not todos_text:
            return
        self.console.print("\nPlan Progress:")
        self.console.print(f"{todos_text}\n")

    def pick(self, title: str, options: List[str]) -> Optional[int]:
        if not options:
            return None
        table = Table(title=f"Choose: {title}", show_header=True)
        table.add_column("#", style="cyan", width=4)
        table.add_column("Option", style="white")

        for i, opt in enumerate(options):
            table.add_row(str(i + 1), opt)

        self.console.print(table)
        try:
            raw = self.console.input("[bold cyan]Enter choice number (or Enter to cancel): [/bold cyan]").strip()
            if not raw.isdigit():
                return None
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
            return None
        except (KeyboardInterrupt, EOFError):
            return None

    def spinner(self, description: str):
        return self.console.status(f"[bold cyan]{description}[/bold cyan]", spinner="dots")


ui = TerminalUI()
