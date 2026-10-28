"""Planner state and dynamic WriteTodos tool."""

from typing import List
from ..core.types import TodoItem, TodoStatus
from ..tools.base import BaseTool

_TODOS: List[TodoItem] = []


class PlannerState:
    """Singleton tracking current active plan and status."""

    @classmethod
    def get_todos(cls) -> List[TodoItem]:
        return list(_TODOS)

    @classmethod
    def set_todos(cls, items: List[TodoItem]) -> str:
        in_progress = [t for t in items if t.status == TodoStatus.IN_PROGRESS]
        if len(in_progress) > 1:
            return f"Error: Exactly one task may be in_progress at any time. Found {len(in_progress)}."

        _TODOS.clear()
        _TODOS.extend(items)
        return cls.render_markdown() or "Todo list cleared."

    @classmethod
    def render_markdown(cls) -> str:
        if not _TODOS:
            return ""
        icons = {
            TodoStatus.PENDING: "[ ]",
            TodoStatus.IN_PROGRESS: "[~]",
            TodoStatus.DONE: "[x]",
        }
        lines = [f"{icons[t.status]} {t.content}" for t in _TODOS]
        return "\n".join(lines)

    @classmethod
    def active_action_form(cls) -> str:
        for t in _TODOS:
            if t.status == TodoStatus.IN_PROGRESS:
                return t.active_form
        return "Thinking..."


class WriteTodosTool(BaseTool):
    name = "write_todos"
    description = (
        "Record and update the multi-step execution plan. "
        "Must send the whole list on each invocation. "
        "Maintain exactly ONE task with status='in_progress', update tasks to 'done' immediately when finished."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Imperative action item (e.g. 'Write unit tests')",
                        },
                        "active_form": {
                            "type": "string",
                            "description": "Present continuous spinner description (e.g. 'Writing unit tests')",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "done"],
                        },
                    },
                    "required": ["content", "active_form", "status"],
                },
            }
        },
        "required": ["todos"],
    }

    def run(self, todos: list) -> str:
        parsed_items = []
        for item in todos:
            parsed_items.append(
                TodoItem(
                    content=item["content"],
                    active_form=item.get("active_form", item.get("activeForm", "Working...")),
                    status=TodoStatus(item["status"]),
                )
            )
        return PlannerState.set_todos(parsed_items)
