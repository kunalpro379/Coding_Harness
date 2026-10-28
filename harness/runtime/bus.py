"""Production EventBus supporting streamed events, subscribers, and distributed traces."""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    run_id: str
    event_type: str
    timestamp: float = Field(default_factory=time.time)
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventBus:
    """Async event bus for broadcasting events across interfaces (TUI, Webhook, Cron)."""

    def __init__(self):
        self._subscribers: List[Callable[[AgentEvent], Any]] = []

    def subscribe(self, callback: Callable[[AgentEvent], Any]):
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AgentEvent], Any]):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def publish(self, run_id: str, event_type: str, payload: Optional[Dict[str, Any]] = None):
        event = AgentEvent(run_id=run_id, event_type=event_type, payload=payload or {})
        for sub in self._subscribers:
            try:
                res = sub(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass


default_event_bus = EventBus()

