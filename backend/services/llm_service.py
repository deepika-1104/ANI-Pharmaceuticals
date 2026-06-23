"""
LLM service — thin facade over llm.client.LLMClient.

Exposes the same public API that the rest of the codebase expects:
  generate_response(...)   → str
  stream_response(...)     → AsyncGenerator[str, None]
  check_llm_health()       → dict

All provider configuration lives in config/settings.py.
Model selection and token management are handled by llm/client.py.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from llm.client import get_llm_client
from prompts.builder import PromptContext, build_system_prompt as _build_prompt

logger = logging.getLogger("voxa.services.llm")

MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_MSG_CHARS = 1_000
MAX_DATA_CONTEXT_CHARS = 28_000


def _build_messages(
    user_query: str,
    data_context: str = "",
    conversation_history: Optional[list[dict]] = None,
) -> list[dict]:
    safe_ctx = (
        data_context[:MAX_DATA_CONTEXT_CHARS]
        + ("\n\n[DATA CONTEXT TRUNCATED]" if len(data_context) > MAX_DATA_CONTEXT_CHARS else "")
    ) if data_context else ""

    system_content = _build_prompt(PromptContext(data_context=safe_ctx))
    messages: list[dict] = [{"role": "system", "content": system_content}]

    if conversation_history:
        for msg in conversation_history[-MAX_HISTORY_MESSAGES:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                if len(content) > MAX_HISTORY_MSG_CHARS:
                    content = content[:MAX_HISTORY_MSG_CHARS] + " …[truncated]"
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_query})
    return messages


def generate_response(
    user_query: str,
    data_context: str = "",
    conversation_history: Optional[list[dict]] = None,
    model: Optional[str] = None,
) -> str:
    """Synchronous LLM call. Returns the generated text."""
    messages = _build_messages(user_query, data_context, conversation_history)
    return get_llm_client().complete(messages, model)


async def stream_response(
    user_query: str,
    data_context: str = "",
    conversation_history: Optional[list[dict]] = None,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Async streaming LLM call. Yields text tokens as they arrive."""
    messages = _build_messages(user_query, data_context, conversation_history)
    async for token in get_llm_client().stream(messages, model):
        yield token


def check_llm_health() -> dict:
    return get_llm_client().health_check()
