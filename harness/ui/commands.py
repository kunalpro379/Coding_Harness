"""Interactive Slash Command Handlers (/rewind, /sessions, /compact, /plan, /help)."""

from typing import List, Tuple
from ..core.types import Message, Role
from ..memory.compactor import compactor
from ..memory.session import session_manager
from ..memory.trimmer import trimmer
from ..tools.planner import PlannerState
from ..ui.terminal import ui

SLASH_COMMANDS = {
    "/help": "Display list of available slash commands",
    "/plan": "Inspect or clear active development task list",
    "/compact": "Force-compact history right now to recover context window",
    "/rewind": "Rewind transcript to an earlier conversational turn",
    "/sessions": "Browse and resume a past conversation session",
}


def preview_message(msg: Message) -> str:
    if msg.tool_calls:
        calls = ", ".join(c.function.name for c in msg.tool_calls)
        return f"-> Tool Call: {calls}"
    content = msg.content or ""
    return " ".join(content.split())[:75]


class CommandHandler:
    """Dispatches user commands beginning with '/'."""

    @staticmethod
    def handle(cmd: str, messages: List[Message]) -> Tuple[List[Message], bool]:
        """Returns (updated_messages, should_save)."""
        cmd = cmd.strip()

        if cmd == "/help":
            ui.note("Available Slash Commands:")
            for c, desc in SLASH_COMMANDS.items():
                ui.note(f"  {c:<12} {desc}")
            return messages, False

        if cmd == "/plan":
            plan_str = PlannerState.render_markdown()
            if not plan_str:
                ui.note("No active plan. The agent creates plans automatically using 'write_todos'.")
            else:
                ui.display_plan(plan_str)
            return messages, False

        if cmd == "/compact":
            before_len = len(messages)
            with ui.spinner("Performing LLM transcript compaction..."):
                compacted = compactor.compact(messages)

            if len(compacted) == before_len:
                ui.note("Transcript is not long enough to compact.")
                return messages, False

            session_manager.record_compaction(compacted)
            ui.success(f"Compacted transcript: {before_len} messages -> {len(compacted)} messages.")
            return compacted, True

        if cmd == "/rewind":
            rows = [f"[{m.role.value:<9}] {preview_message(m)}" for m in messages]
            choice = ui.pick("Select message index to rewind to", rows)
            if choice is None:
                ui.note("Rewind cancelled.")
                return messages, False

            target_count = choice + 1
            session_manager.record_rewind(target_count)
            rewound_messages = messages[:target_count]
            ui.success(f"Rewound session to turn #{target_count}.")
            return rewound_messages, True

        if cmd == "/sessions":
            sessions = session_manager.list_sessions()
            if not sessions:
                ui.note("No saved sessions found.")
                return messages, False

            rows = [f"{s['id']}  {s['title']}" for s in sessions]
            choice = ui.pick("Open Previous Session", rows)
            if choice is None:
                return messages, False

            selected_id = sessions[choice]["id"]
            restored = session_manager.load_session(selected_id)
            trimmer.strip_turn(restored)
            ui.success(f"Resumed session '{selected_id}' ({len(restored)} messages loaded).")
            return restored, True

        ui.note(f"Unknown command '{cmd}'. Available: {', '.join(SLASH_COMMANDS.keys())}")
        return messages, False


command_handler = CommandHandler()
