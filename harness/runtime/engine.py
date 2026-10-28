"""Headless Harness Runtime & Execution Engine.

Decouples the core agent loop from interfaces (TUI, CLI, Webhook, Cron)
and coordinates background execution, parallel runs, context compaction, and events.
"""

import asyncio
import uuid
from typing import Any, Dict, List, Optional
from ..core.config import settings
from ..core.types import Message, Role
from ..memory.compactor import compactor
from ..memory.observer import observer
from ..memory.session import session_manager
from ..memory.trimmer import trimmer
from ..providers.llm import LLMClient
from ..services.ledger import default_ledger
from ..services.tracer import default_tracer
from ..tools.base import ToolRegistry, registry
from ..tools.planner import PlannerState
from ..ui.terminal import TerminalUI, ui
from .bus import EventBus, default_event_bus
from .steering import PriorityGate, SteeringQueue
from .store import AgentRun, RunStatus, RunStore, default_run_store


class HeadlessHarness:
    """Reusable, Headless Agent Execution Engine.

    Can be invoked by interactive TUI, background workers, webhooks, or cron.
    """

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
        event_bus: Optional[EventBus] = None,
        run_store: Optional[RunStore] = None,
    ):
        self.llm = llm or LLMClient()
        self.registry = tool_registry or registry
        self.ui = ui_handler or ui
        self.event_bus = event_bus or default_event_bus
        self.run_store = run_store or default_run_store

        self.steering_queue = SteeringQueue()
        self.priority_gate = PriorityGate(self.steering_queue)

    async def execute_task(
        self,
        task: str,
        run_id: Optional[str] = None,
        initial_messages: Optional[List[Message]] = None,
        max_steps: Optional[int] = None,
    ) -> str:
        """Run an autonomous task through the headless agent loop asynchronously."""
        run_id = run_id or f"run_{uuid.uuid4().hex[:10]}"
        run = self.run_store.create(run_id=run_id, task=task)
        run.status = RunStatus.RUNNING
        self.run_store.save(run)

        await self.event_bus.publish(run_id, "run.started", {"task": task})

        messages = list(initial_messages) if initial_messages else []
        if not messages or messages[0].role != Role.SYSTEM:
            from ..agents.lead import LEAD_SYSTEM_PROMPT_TEMPLATE
            from ..tools.skills import skill_manager
            skills_list = "\n".join(f"  - {k}: {v}" for k, v in skill_manager.list_skills().items())
            sys_prompt = LEAD_SYSTEM_PROMPT_TEMPLATE.format(
                workspace=str(settings.workspace_root),
                skills_list=skills_list,
            )
            messages.insert(0, Message(role=Role.SYSTEM, content=sys_prompt))

        messages.append(Message(role=Role.USER, content=task))

        limit_steps = max_steps or settings.max_run_steps
        step_number = 0
        final_answer = ""

        try:
            while step_number < limit_steps:
                # 1. Safe Boundary Check for user steering interruptions
                steer_msgs = self.priority_gate.checkpoint_safe_boundary()
                if steer_msgs:
                    for s in steer_msgs:
                        await self.event_bus.publish(run_id, "run.steered", {"content": s.content})
                        messages.append(Message(role=Role.USER, content=f"[Mid-turn constraint]: {s.content}"))

                # 2. Late context injection
                injection_msg = observer.build_injection(todos_text=PlannerState.render_markdown())
                max_budget = int(settings.context_window * settings.compact_at)
                trimmer.fit_budget(messages, max_budget=max_budget)

                if messages[-1].role == Role.TOOL:
                    full_context = list(messages)
                else:
                    full_context = messages + [injection_msg]

                step_number += 1
                await self.event_bus.publish(run_id, "step.started", {"step": step_number})

                # 3. Model call
                response = await asyncio.to_thread(
                    self.llm.complete,
                    messages=full_context,
                    tools=self.registry.get_schemas(),
                )

                assistant_msg = response.message
                messages.append(assistant_msg)
                session_manager.save(messages)

                await self.event_bus.publish(
                    run_id,
                    "model.response",
                    {
                        "content": assistant_msg.content,
                        "tool_calls": len(assistant_msg.tool_calls or []),
                        "usage": response.usage.model_dump(),
                    },
                )

                if assistant_msg.content:
                    final_answer = assistant_msg.content

                # Check if turn is done
                if not assistant_msg.tool_calls:
                    break

                # 4. Execute tool calls under Priority Gate tracking
                for tool_call in assistant_msg.tool_calls:
                    fn_name = tool_call.function.name
                    import json
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except Exception:
                        args = {}

                    self.priority_gate.on_tool_start()
                    await self.event_bus.publish(run_id, "tool.start", {"name": fn_name, "args": args})

                    # Execute in worker thread
                    raw_result = await asyncio.to_thread(
                        self.registry.execute,
                        name=fn_name,
                        arguments=args,
                        ui_approver=self.ui.approve,
                    )
                    capped_result = trimmer.cap(raw_result)

                    self.priority_gate.on_tool_end()
                    await self.event_bus.publish(run_id, "tool.end", {"name": fn_name, "result_preview": capped_result[:150]})

                    messages.append(
                        Message(
                            role=Role.TOOL,
                            tool_call_id=tool_call.id,
                            content=capped_result,
                        )
                    )
                    session_manager.save(messages)

            # Cleanup & check context compaction
            trimmer.sweep()
            trimmer.strip_turn(messages)

            run.status = RunStatus.COMPLETED
            run.result = final_answer
            self.run_store.save(run)
            await self.event_bus.publish(run_id, "run.completed", {"result": final_answer})
            return final_answer

        except Exception as e:
            run.status = RunStatus.FAILED
            run.error = str(e)
            self.run_store.save(run)
            await self.event_bus.publish(run_id, "run.failed", {"error": str(e)})
            raise

