"""
Follow-up suggestion engine.

After each non-conversational response, generates 3-4 short follow-up
questions the user might naturally ask next.  Questions are driven by:
  - what the user just asked
  - which collections were queried
  - the first snippet of the LLM response

The suggestions are returned to the frontend as part of the WebSocket
{"done": true, "followups": [...]} frame so they can be rendered as
clickable chips beneath the response.
"""

from __future__ import annotations

import logging
import re

from llm.client import LLMClient

logger = logging.getLogger("voxa.orchestrator.followup")

_SYSTEM = """\
You are an analytics assistant for an enterprise data platform.
Given context about what a user just queried and what data was returned,
suggest 3-4 concise natural-language follow-up questions they might ask next.

Rules:
- Each question must be self-contained and answerable from database data
- Vary types: drill-down, comparison, trend, anomaly, or action
- Maximum 15 words per question
- Return ONLY a plain numbered list — no headers, no explanations
- Do NOT suggest summarizing the conversation, reviewing chat history, or any
  meta-conversational questions about the assistant or prior turns
- Do NOT suggest questions about the assistant's capabilities or how it works

Example output:
1. Which plant had the highest defect rate last month?
2. How does revenue this quarter compare to last quarter?
3. Show the top 5 doctors by patient count this week.
4. List all quality alerts with severity above 3.
"""

_LIST_LINE_RE = re.compile(r"^\s*[\d\-\*•]+[.):\s]+", re.M)


async def generate_followups(
    query: str,
    response_snippet: str,
    collections_used: list[str],
    llm: LLMClient,
) -> list[str]:
    """
    Return up to 4 follow-up question strings.
    Returns [] silently on any error — follow-ups are optional.
    """
    if not query:
        return []

    context = (
        f"User query: {query}\n"
        f"Collections queried: {', '.join(collections_used) or 'none'}\n"
        f"Response (first 400 chars): {response_snippet[:400]}"
    )

    try:
        raw = llm.complete(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": context},
            ]
        )
        suggestions: list[str] = []
        for line in raw.strip().splitlines():
            # Strip leading list markers like "1.", "-", "•"
            clean = _LIST_LINE_RE.sub("", line).strip()
            if clean and len(clean) > 5:
                suggestions.append(clean)
        suggestions = suggestions[:4]
        logger.info("Follow-ups generated: %d", len(suggestions))
        return suggestions
    except Exception as exc:
        logger.warning("Follow-up generation failed: %s", exc)
        return []
