"""Parallel Execution Engine & Dynamic Subagent Spawner.

Spawns multiple autonomous subagents asynchronously to solve subtasks in parallel
(e.g., parallel file inspection, independent module investigation, or test running).
"""

import asyncio
import uuid
from typing import Any, Callable, Dict, List, Optional
from ..agents.factory import AgentFactory
from ..core.types import Message, Role
from ..providers.llm import LLMClient
from ..tools.base import BaseTool, ToolRegistry, registry
from ..ui.terminal import TerminalUI, ui
from .bus import EventBus, default_event_bus


class SubtaskSpec:
    def __init__(self, task_id: str, prompt: str, agent_type: str = "explorer"):
        self.task_id = task_id
        self.prompt = prompt
        self.agent_type = agent_type


class ParallelAgentSpawner:
    """Async engine for dispatching and aggregating concurrent subagent executions."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ui_handler: Optional[TerminalUI] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.llm = llm or LLMClient()
        self.registry = tool_registry or registry
        self.ui = ui_handler or ui
        self.event_bus = event_bus or default_event_bus

    async def _run_single_agent(self, task_id: str, prompt: str, agent_type: str) -> Dict[str, Any]:
        """Worker executing one subagent in an isolated context asynchronously."""
        await self.event_bus.publish(task_id, "subagent.spawned", {"type": agent_type, "prompt": prompt[:100]})
        
        # Instantiate ephemeral isolated agent
        if agent_type == "researcher":
            agent = AgentFactory.create_researcher(llm=self.llm, tool_registry=self.registry, ui_handler=self.ui)
        elif agent_type == "reviewer":
            agent = AgentFactory.create_reviewer(llm=self.llm, tool_registry=self.registry, ui_handler=self.ui)
        else:
            agent = AgentFactory.create_explorer(llm=self.llm, tool_registry=self.registry, ui_handler=self.ui)

        # Run agent in background thread pool to avoid blocking async event loop
        report = await asyncio.to_thread(agent.run, prompt)
        
        await self.event_bus.publish(task_id, "subagent.completed", {"summary": report[:150]})
        return {
            "task_id": task_id,
            "agent_type": agent_type,
            "prompt": prompt,
            "report": report,
            "status": "success",
        }

    async def run_parallel_tasks(self, tasks: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Spawn multiple subagents simultaneously using asyncio.gather."""
        coroutines = []
        for i, t in enumerate(tasks):
            t_id = t.get("id") or f"subtask_{uuid.uuid4().hex[:6]}"
            prompt = t.get("prompt") or t.get("task") or ""
            agent_type = t.get("agent_type") or "explorer"
            coroutines.append(self._run_single_agent(t_id, prompt, agent_type))

        results = await asyncio.gather(*coroutines, return_exceptions=True)
        final_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                final_results.append({
                    "task_id": f"subtask_{i}",
                    "status": "error",
                    "error": str(res),
                })
            else:
                final_results.append(res)
        return final_results


class DelegateParallelTasksTool(BaseTool):
    """Tool allowing Lead Agent to delegate work to multiple subagents concurrently."""

    name = "delegate_parallel_tasks"
    description = (
        "Spawn multiple subagents in parallel to execute independent investigations or subtasks asynchronously. "
        "Each subagent runs in its own context window without interfering with others. "
        "Returns synthesized findings from all subagents simultaneously."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Specific goal or question for this subagent.",
                        },
                        "agent_type": {
                            "type": "string",
                            "enum": ["explorer", "researcher", "reviewer"],
                            "description": "Type of subagent to spawn (explorer for code, researcher for web, reviewer for audit).",
                        },
                    },
                    "required": ["prompt"],
                },
                "description": "List of subtasks to execute concurrently in parallel.",
            }
        },
        "required": ["tasks"],
    }

    def __init__(self, spawner: Optional[ParallelAgentSpawner] = None):
        self.spawner = spawner or ParallelAgentSpawner()

    def run(self, tasks: List[Dict[str, str]]) -> str:
        if not tasks:
            return "No tasks specified for parallel delegation."

        # Run event loop for async parallel execution
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If called inside an existing running loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.spawner.run_parallel_tasks(tasks))
                results = future.result()
        else:
            results = loop.run_until_complete(self.spawner.run_parallel_tasks(tasks))

        formatted = ["=== Parallel Subagents Synthesis Results ==="]
        for res in results:
            if res.get("status") == "success":
                formatted.append(f"\n[Subagent: {res['agent_type']} | Task: {res['prompt'][:60]}...]")
                formatted.append(res["report"])
            else:
                formatted.append(f"\n[Subagent Failed: {res.get('error')}]")

        return "\n".join(formatted)

