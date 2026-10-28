"""Lead Developer Agent orchestrating planning, tool execution, and context management."""

import json
from typing import List, Optional
from ..core.config import settings
from ..core.types import Message, Role
from ..memory.compactor import compactor
from ..memory.observer import observer
from ..memory.session import session_manager
from ..memory.trimmer import trimmer
from ..providers.llm import LLMClient
from ..tools.base import ToolRegistry
from ..tools.planner import PlannerState
from ..tools.skills import skill_manager
from ..ui.terminal import TerminalUI
from .base import BaseAgent

LEAD_SYSTEM_PROMPT_TEMPLATE = r"""
You are Cursor Agent, an elite principal software engineer and autonomous pair programmer.
You solve difficult coding, debugging, and system engineering requests autonomously, reliably, and with exceptional quality.

Thinking & Output Guidelines:
- Express your internal reasoning and deliberation inside <thought>...</thought> tags before taking actions.
  In this thought block, explain clearly what you are thinking, what hypotheses you are considering, and what questions you are asking yourself.
- Do NOT use emojis anywhere in your messages, thoughts, or responses.
- After or alongside your thoughts, provide clean, concise responses in plain text.

Core Operational Protocol: Plan -> Think -> Act -> Reason -> Verify -> Loop
1. PLAN & BREAK DOWN:
   - For ANY non-trivial task or request requiring more than 1 action, IMMEDIATELY call 'write_todos' first.
   - Establish a concrete roadmap (e.g. Investigation, Implementation, Verification).
   - Keep exactly ONE step with status='in_progress', and mark steps 'done' as soon as they complete.

2. THINK & HYPOTHESIZE:
   - Before editing files or running scripts, formulate an explicit hypothesis of the root cause or required design.
   - Read the exact lines and search code symbols with 'read_file', 'grep_code', or 'search_files'. Never guess line numbers or filenames.

3. ACT & SURGICAL EXECUTION:
   - Use 'str_replace' for precise edits, including enough surrounding lines to ensure unique matching.
   - Use 'write_file' to create new components, tests, and configuration files.
   - Use 'bash' to run build tools, package managers (npm, pip), unit tests, or server commands.

4. BROWSER RESEARCH & ERROR DIAGNOSTICS:
   - Whenever an unfamiliar error, dependency conflict, or library API question arises:
     * Call 'web_search' to query GitHub issues, StackOverflow, or official documentation.
     * Call 'browser_fetch' to read documentation pages or solution articles.
     * Do NOT repeatedly run the exact same failing command without changing anything.

5. VERIFY & CHECK OUTPUT (MANDATORY):
   - ALWAYS verify your changes after editing.
   - Run tests, compile checks, linters, or check health/status endpoints via 'bash'.
   - Inspect the stdout/stderr. If exit code != 0 or there are error logs, diagnose and fix them immediately.

6. HUMAN-IN-THE-LOOP (JUDICIOUS USE):
   - 'ask_human': Call this tool ONLY when:
     * Requirements are fundamentally ambiguous with multiple conflicting user goals.
     * External credentials/tokens/secrets are needed.
     * A major architectural tradeoff needs user decision.
   - Do NOT ask trivial questions that you can verify autonomously by inspecting code or running checks.

- Parallel Subagent Delegation:
  * When you have multiple independent tasks (e.g. investigating 3 different modules, scanning files, running checks),
    call 'delegate_parallel_tasks' to spawn multiple subagents asynchronously in parallel.
  * Each subagent runs in its own isolated context window simultaneously and returns a combined synthesized report.

Environment & Capabilities:
- Workspace root: {workspace}
- System Access: Full OS access. You can search, inspect, read, or edit ANY file across the entire machine or workspace.
- Shell Execution: 'bash' runs commands on the system. Supports optional 'cwd' and 'timeout'.
- Desktop Automation: 'desktop_screenshot', 'desktop_get_windows', 'desktop_mouse', 'desktop_keyboard', 'desktop_launch'.
- Skills & Playbooks:
{skills_list}
"""


class LeadAgent(BaseAgent):
    """Main orchestrator coordinating user interaction, planning, and tool dispatch."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
    ):
        skills_summary = "\n".join(
            f"  - {name}: {desc}" for name, desc in skill_manager.list_skills().items()
        ) or "  (No custom skills installed)"

        system_prompt = LEAD_SYSTEM_PROMPT_TEMPLATE.format(
            workspace=str(settings.workspace_root),
            skills_list=skills_summary,
        )

        super().__init__(
            name="LeadAgent",
            role_description="Principal Autonomous Software Engineer",
            system_prompt=system_prompt,
            llm=llm,
            tool_registry=tool_registry,
            ui_handler=ui_handler,
        )

    def run(self, user_input: str, messages: List[Message], debug: bool = False) -> List[Message]:
        """Delegate to run_turn to satisfy BaseAgent abstract interface."""
        return self.run_turn(user_input, messages, debug=debug)

    def run_turn(self, user_input: str, messages: List[Message], debug: bool = False) -> List[Message]:
        """Execute a full turn: user message -> plan & tool loop -> context trimming -> compaction check."""
        messages.append(Message(role=Role.USER, content=user_input))

        # Reset per-turn step counter so each turn gets a fresh step budget
        from ..services.ledger import default_ledger
        from ..services.tracer import default_tracer
        default_ledger.steps = 0

        last_usage = None
        step_number = 0

        while True:
            # 1. Late context injection (Git diffs, todos, time)
            # Only inject if last message is a user message, otherwise prepend to current turn
            injection_msg = observer.build_injection(todos_text=PlannerState.render_markdown())

            # 2. Check token budget & drop if emergency
            max_budget = int(settings.context_window * settings.compact_at)
            dropped = trimmer.fit_budget(messages, max_budget=max_budget)
            if dropped > 0:
                self.ui.note(f"Preserved context window by shedding {dropped} historical tool outputs.")

            # 3. Call LLM: ensure the last message before completion is properly ordered
            # If the last message is a tool response, do NOT append a user message after it,
            # because OpenAI/Nemotron requires all tool results to directly follow the assistant tool call.
            if messages[-1].role == Role.TOOL:
                full_context = list(messages)
            else:
                full_context = messages + [injection_msg]

            default_ledger.steps += 1
            step_number += 1
            if default_ledger.is_budget_exceeded():
                self.ui.warning("Run budget exceeded. Halting turn execution.")
                break
            if default_ledger.is_step_limit_reached():
                self.ui.warning("Run step limit reached. Concluding turn.")
                break

            self.ui.display_step(step_number)

            spinner_text = PlannerState.active_action_form()
            with self.ui.spinner(spinner_text):
                response = self.llm.complete(
                    messages=full_context,
                    tools=self.registry.get_schemas(),
                )

            last_usage = response.usage
            assistant_msg = response.message
            messages.append(assistant_msg)
            session_manager.save(messages)

            default_ledger.charge_llm(response.usage)
            default_tracer.log("model_step", step=default_ledger.steps, usd=round(default_ledger.usd, 4))

            self.ui.display_usage(response.usage)
            if debug and assistant_msg.content:
                self.ui.note(f"[DEBUG]: {assistant_msg.content[:200]}...")

            if assistant_msg.content:
                self.ui.assistant_message(assistant_msg.content)

            # If no tools called, the agent has finished speaking for this turn
            if not assistant_msg.tool_calls:
                break

            # 4. Execute tool calls
            for tool_call in assistant_msg.tool_calls:
                fn_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as err:
                    args = {}
                    result = f"Error: Failed to parse tool arguments JSON: {err}"
                else:
                    raw_result = self.registry.execute(
                        name=fn_name,
                        arguments=args,
                        ui_approver=self.ui.approve,
                    )
                    # Cap large fresh outputs & spill to disk
                    result = trimmer.cap(raw_result)

                self.ui.tool_execution(fn_name, args, result)
                if fn_name == "write_todos":
                    self.ui.display_plan(PlannerState.render_markdown())

                messages.append(
                    Message(
                        role=Role.TOOL,
                        tool_call_id=tool_call.id,
                        content=result,
                    )
                )
                session_manager.save(messages)

        # 5. End of turn cleanup: sweep spilled files, strip old tool outputs
        trimmer.sweep()
        trimmer.strip_turn(messages)

        # 6. Check if compaction is needed
        if last_usage and compactor.is_needed(last_usage):
            self.ui.note("Context threshold reached. Initiating automatic compaction...")
            messages = compactor.compact(messages)
            session_manager.record_compaction(messages)

        return messages
