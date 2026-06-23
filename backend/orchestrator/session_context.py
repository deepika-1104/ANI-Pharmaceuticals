"""
Per-session analytical context store.

Tracks what the user was discussing so follow-up queries like
"same plant" or "those models" resolve correctly — zero LLM tokens.

Stored in-process (thread-safe).  No persistence across server restarts,
which is intentional: context is conversational, not durable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from threading import RLock
from typing import Optional


@dataclass
class AnalyticalContext:
    """Analytical state for one conversation session."""

    # Entities recently mentioned (plants, doctors, models, products …)
    active_entities: list[str] = field(default_factory=list)

    # Last data metric discussed ("revenue", "production_volume", "patient_count" …)
    active_metric: Optional[str] = None

    # Last time range expressed as the user said it ("this week", "last month" …)
    active_time_range: Optional[str] = None

    # Collections that produced data in the previous turn
    active_collections: list[str] = field(default_factory=list)

    # Intent of the last classified query
    last_intent: Optional[str] = None

    # Raw query from the previous turn
    last_query: Optional[str] = None

    # First 300 chars of the last LLM response (used by follow-up engine)
    last_response_snippet: Optional[str] = None


# ── Time-range extraction helpers ────────────────────────────────────────────

_TIME_RANGE_RE = re.compile(
    r"""
    (?:
        (?:this|last|previous|next|past)\s+
        (?:week|month|quarter|year|day|fortnight)
    )
    |
    (?:
        \d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?   # dates like 01/01/2025
    )
    |
    (?:
        (?:january|february|march|april|may|june|july|august
          |september|october|november|december)
        (?:\s+\d{4})?
    )
    |
    (?:
        q[1-4]\s*\d{4}                         # Q1 2025
    )
    |
    (?:
        (?<!\d)(?:19|20)\d{2}(?!\d)             # plain year 1900-2099, not part
    )                                           # of a longer digit run (IDs, counts)
    """,
    re.VERBOSE | re.I,
)


def extract_time_range(query: str) -> Optional[str]:
    """Return the first time expression found in *query*, or None."""
    m = _TIME_RANGE_RE.search(query)
    return m.group(0).strip() if m else None


# ── Session store ─────────────────────────────────────────────────────────────


class SessionContextStore:
    """Thread-safe in-process map: session_id → AnalyticalContext."""

    _MAX_ENTITIES = 12

    def __init__(self) -> None:
        self._store: dict[str, AnalyticalContext] = {}
        self._lock = RLock()

    def get(self, session_id: str) -> AnalyticalContext:
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = AnalyticalContext()
            return self._store[session_id]

    def update(
        self,
        session_id: str,
        *,
        entities: Optional[list[str]] = None,
        metric: Optional[str] = None,
        time_range: Optional[str] = None,
        collections: Optional[list[str]] = None,
        intent: Optional[str] = None,
        query: Optional[str] = None,
        response_snippet: Optional[str] = None,
    ) -> None:
        ctx = self.get(session_id)
        with self._lock:
            if entities:
                merged = list(dict.fromkeys(entities + ctx.active_entities))
                ctx.active_entities = merged[: self._MAX_ENTITIES]
            if metric is not None:
                ctx.active_metric = metric
            if time_range is not None:
                ctx.active_time_range = time_range
            if collections is not None:
                ctx.active_collections = list(collections)
            if intent is not None:
                ctx.last_intent = intent
            if query is not None:
                ctx.last_query = query
            if response_snippet is not None:
                ctx.last_response_snippet = response_snippet[:300]

    def reset_topic(self, session_id: str) -> None:
        """
        Clear entity/metric/time context when the conversation changes topic,
        so stale state never leaks into an unrelated standalone query.
        last_query / last_response_snippet are kept for follow-up generation.
        """
        ctx = self.get(session_id)
        with self._lock:
            ctx.active_entities = []
            ctx.active_metric = None
            ctx.active_time_range = None
            ctx.active_collections = []

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)


# ── Singleton ─────────────────────────────────────────────────────────────────

_store: Optional[SessionContextStore] = None


def get_context_store() -> SessionContextStore:
    global _store
    if _store is None:
        _store = SessionContextStore()
    return _store
