"""Data models for messages, tool calls, tokens, and multi-agent communications."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FunctionCall(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: FunctionCall


class Message(BaseModel):
    role: Role
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard OpenAI Chat Completion format."""
        data = self.model_dump(exclude_none=True)
        data["role"] = self.role.value
        return data


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: Optional[int] = 0
    cached_tokens: Optional[int] = 0
    total_tokens: int = 0

    @classmethod
    def from_response(cls, usage: Any) -> "TokenUsage":
        if not usage:
            return cls()
        completion_details = getattr(usage, "completion_tokens_details", None)
        prompt_details = getattr(usage, "prompt_tokens_details", None)

        prompt = getattr(usage, "prompt_tokens", 0) or 0
        completion = getattr(usage, "completion_tokens", 0) or 0
        total = getattr(usage, "total_tokens", prompt + completion) or (prompt + completion)

        return cls(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            reasoning_tokens=getattr(completion_details, "reasoning_tokens", 0) if completion_details else 0,
            cached_tokens=getattr(prompt_details, "cached_tokens", 0) if prompt_details else 0,
        )


class LLMResponse(BaseModel):
    message: Message
    usage: TokenUsage


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TodoItem(BaseModel):
    content: str = Field(description="The imperative task description, e.g. 'Refactor auth controller'")
    active_form: str = Field(description="The present continuous form for spinner, e.g. 'Refactoring auth controller'")
    status: TodoStatus = Field(default=TodoStatus.PENDING)


class AgentHandoff(BaseModel):
    """Structured report handed back between agents."""
    agent_name: str
    summary: str
    key_findings: List[str] = Field(default_factory=list)
    files_inspected: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    next_action_recommendation: Optional[str] = None
