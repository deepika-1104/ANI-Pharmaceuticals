"""
Token budget management for LLM message lists.

We estimate tokens at ~4 characters per token (fast, no tiktoken dependency).
The purpose is to keep total message payload within the model's context window
by trimming conversation history when needed.
"""

MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_MSG_CHARS = 1_000


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def trim_messages(
    messages: list[dict],
    system_char_budget: int,
) -> list[dict]:
    """
    Trim *messages* so the total estimated token count stays within budget.

    Strategy:
    1. Always keep the system message and the last user message.
    2. Truncate the system message if it exceeds *system_char_budget*.
    3. Keep the most recent history messages up to MAX_HISTORY_MESSAGES.
    4. Truncate individual history messages to MAX_HISTORY_MSG_CHARS.
    """
    if not messages:
        return messages

    result: list[dict] = []
    system_msg = None
    history: list[dict] = []
    last_user: dict | None = None

    for msg in messages:
        role = msg.get("role", "")
        if role == "system":
            system_msg = msg
        elif role == "user" and msg is messages[-1]:
            last_user = msg
        else:
            history.append(msg)

    # Trim system message
    if system_msg:
        content = system_msg["content"]
        if len(content) > system_char_budget:
            content = content[:system_char_budget] + "\n\n[CONTEXT TRUNCATED]"
        result.append({"role": "system", "content": content})

    # Keep only recent history, truncating long messages
    for msg in history[-MAX_HISTORY_MESSAGES:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if len(content) > MAX_HISTORY_MSG_CHARS:
            content = content[:MAX_HISTORY_MSG_CHARS] + " …[truncated]"
        result.append({"role": role, "content": content})

    # Always include the last user message
    if last_user:
        result.append(last_user)

    return result
