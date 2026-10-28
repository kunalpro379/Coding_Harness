"""Exceptions hierarchy for the Harness."""


class HarnessException(Exception):
    """Base exception for all agent harness errors."""
    pass


class LLMError(HarnessException):
    """Raised when LLM API call fails or times out."""
    pass


class ContextOverflowError(HarnessException):
    """Raised when transcript exceeds hard limits."""
    pass


class ToolExecutionError(HarnessException):
    """Raised when a tool encounters an unhandled runtime failure."""
    pass


class PolicyDeniedError(HarnessException):
    """Raised when security policy or user rejects tool execution."""
    pass
