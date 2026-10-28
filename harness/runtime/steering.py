"""Steering Queue & Priority Gate for handling user mid-turn interruptions & safe boundaries."""

import asyncio
import time
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SteeringPriority(str, Enum):
    INTERRUPT = "interrupt"  # Immediate direction change
    STEER = "steer"          # Advice or constraint for next model call
    BACKGROUND = "background"


class SteeringMessage(BaseModel):
    content: str
    priority: SteeringPriority = SteeringPriority.STEER
    timestamp: float = Field(default_factory=time.time)


class SteeringQueue:
    """Buffers mid-turn user instructions arriving while tools/model are in-flight."""

    def __init__(self):
        self._queue: List[SteeringMessage] = []

    def push(self, content: str, priority: SteeringPriority = SteeringPriority.STEER):
        self._queue.append(SteeringMessage(content=content, priority=priority))

    def has_pending(self) -> bool:
        return len(self._queue) > 0

    def drain(self) -> List[SteeringMessage]:
        msgs = list(self._queue)
        self._queue.clear()
        return msgs


class PriorityGate:
    """Enforces Safe Boundaries: only yields steering messages before the next Model Call,

    never mid-tool execution.
    """

    def __init__(self, queue: SteeringQueue):
        self.queue = queue
        self.tool_in_flight: bool = False

    def on_tool_start(self):
        self.tool_in_flight = True

    def on_tool_end(self):
        self.tool_in_flight = False

    def checkpoint_safe_boundary(self) -> Optional[List[SteeringMessage]]:
        """Safe Boundary check right before Next Model Call.

        If tool is in flight, holds messages.
        """
        if self.tool_in_flight:
            return None
        if self.queue.has_pending():
            return self.queue.drain()
        return None
