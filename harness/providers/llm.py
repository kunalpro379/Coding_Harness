"""Production LLM Client wrapper with error handling, retries, and token accounting."""

import logging
from typing import Any, Dict, List, Optional
from openai import OpenAI
from ..core.config import settings
from ..core.exceptions import LLMError
from ..core.types import LLMResponse, Message, Role, TokenUsage

logger = logging.getLogger(__name__)


class LLMClient:
    """Enterprise client managing OpenAI compatible API completion requests."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.base_url = base_url or settings.base_url
        self.api_key = api_key or settings.api_key
        self.default_model = model or settings.model

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Execute chat completion and return strongly-typed LLMResponse."""
        target_model = model or self.default_model
        formatted_messages = [m.to_dict() for m in messages]

        request_kwargs: Dict[str, Any] = {
            "model": target_model,
            "messages": formatted_messages,
            "temperature": temperature,
            "top_p": 0.95,
            "max_tokens": 16384,
        }
        if "nemotron" in target_model.lower():
            request_kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True}}

        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["parallel_tool_calls"] = True

        max_retries = 3
        last_error = None
        response = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(**request_kwargs)
                break
            except Exception as e:
                last_error = e
                err_str = str(e)
                logger.warning(f"LLM API attempt {attempt}/{max_retries} failed with {target_model}: {err_str}")
                # If error is a 500 from thinking template or server hiccup, retry after brief delay
                if attempt < max_retries:
                    import time
                    # If 500 error, sometimes the extra thinking kwargs causes NVIDIA NIM internal error on tool turns
                    if "500" in err_str and "extra_body" in request_kwargs:
                        logger.info("Retrying without extra_body chat_template_kwargs...")
                        request_kwargs.pop("extra_body", None)
                    time.sleep(2 * attempt)
                else:
                    logger.error(f"LLM API failure with model {target_model}: {e}")
                    raise LLMError(f"Failed to communicate with LLM provider ({target_model}): {e}") from e

        choice = response.choices[0].message

        # Map response to our internal domain Message
        tool_calls = None
        if getattr(choice, "tool_calls", None):
            from ..core.types import FunctionCall, ToolCall
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    type="function",
                    function=FunctionCall(
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    ),
                )
                for tc in choice.tool_calls
            ]

        res_msg = Message(
            role=Role(choice.role),
            content=choice.content,
            tool_calls=tool_calls,
        )

        usage = TokenUsage.from_response(response.usage)
        return LLMResponse(message=res_msg, usage=usage)


# Global default client instance
default_llm = LLMClient()
