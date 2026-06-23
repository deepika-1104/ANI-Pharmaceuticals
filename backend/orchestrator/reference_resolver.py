"""
Reference resolver — substitutes anaphoric references in user queries
using the session's AnalyticalContext.  Zero LLM calls, zero tokens.

Examples
--------
"Show me the same data for last month"   → last_query context injected
"Those plants again"                     → active_entities substituted
"Compare it with this week"              → active_time_range substituted
"""

from __future__ import annotations

import re

from orchestrator.session_context import AnalyticalContext

# ── Follow-up detection stop-words ───────────────────────────────────────────

_OVERLAP_STOP = {
    "show", "list", "give", "tell", "find", "what", "which", "have", "many",
    "much", "more", "most", "some", "very", "also", "only", "just", "last",
    "this", "that", "with", "from", "about", "over", "into", "like", "make",
    "take", "come", "know", "need", "want", "help", "good", "great", "best",
    "data", "records", "details", "information", "status", "overview", "total",
    "count", "number", "current", "latest", "recent", "right", "next", "back",
    "here", "there", "each", "every", "high", "high", "name", "type", "date",
    "time", "year", "month", "week", "today", "active", "inactive",
}


def _overlap_tokens(text: str) -> set[str]:
    """Extract meaningful lowercase tokens for topic-overlap comparison."""
    tokens = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return {t for t in tokens if len(t) >= 5 and t not in _OVERLAP_STOP}

# ── Substitution patterns ──────────────────────────────────────────────────────
#
# Patterns must only match *unambiguous* anaphora. Bare pronouns ("it", "them",
# "they") and bare "same" appear constantly in ordinary standalone questions
# ("is it improving?", "the same diagnosis") — substituting entity lists into
# them corrupts the query and poisons every downstream pipeline stage.

# Entity references: replace with the most recently active entities
_ENTITY_PATTERNS = [
    re.compile(r"\bthe same ones?\b", re.I),
    re.compile(r"\b(?:those|these)\s+(?:ones?|items?|records?|results?|entities)\b", re.I),
    # Trailing pronoun: "show them", "what about those?" — pronoun ends the query
    re.compile(r"\b(?:them|those|these)\s*\??\s*$", re.I),
    # "the same" only when NOT modifying a noun: "show me the same for March"
    # but not "patients with the same diagnosis"
    re.compile(r"\bthe same\b(?=\s+(?:for|as|in|on|but|over|during)\b|\s*[?.!,]|\s*$)", re.I),
]

# Time references: replace with active_time_range
_TIME_PATTERNS = [
    re.compile(r"\b(?:the\s+)?(?:last time|same period|same time|same dates?|same week|same month)\b", re.I),
    re.compile(r"\b(previous query|as before)\b", re.I),
]

# "the previous metric" → active_metric
_METRIC_PATTERNS = [
    re.compile(r"\b(same metric|that metric)\b", re.I),
    re.compile(r"\b(same (number|figure|value|stat))\b", re.I),
]


def resolve_references(query: str, ctx: AnalyticalContext) -> str:
    """
    Return *query* with anaphoric references substituted from *ctx*.
    Substitutions are applied conservatively — only when context is available.
    """
    resolved = query

    # Substitute time references
    if ctx.active_time_range:
        for pat in _TIME_PATTERNS:
            resolved = pat.sub(ctx.active_time_range, resolved)

    # Substitute entity references
    if ctx.active_entities:
        entity_str = ", ".join(ctx.active_entities[:3])
        for pat in _ENTITY_PATTERNS:
            if pat.search(resolved):
                resolved = pat.sub(entity_str, resolved, count=1)
                break  # only replace one pattern per pass to avoid over-substitution

    # Substitute metric references
    if ctx.active_metric:
        for pat in _METRIC_PATTERNS:
            resolved = pat.sub(ctx.active_metric, resolved)

    if resolved != query:
        # Log what changed — helps with debugging, no PII exposed
        from logging import getLogger
        getLogger("voxa.orchestrator.resolver").debug(
            "Reference resolved: %r → %r", query[:80], resolved[:80]
        )

    return resolved


def is_followup_query(query: str, ctx: AnalyticalContext) -> bool:
    """
    Return True if *query* is a follow-up to the current session context,
    False if it is a standalone (unrelated) question.

    Rules (evaluated in order):
    1. No prior context → always standalone.
    2. Explicit anaphoric marker present → follow-up.
    3. At least one meaningful topic token (5-char prefix) overlaps between
       the query and the session's entities / collections / last query → follow-up.
    4. Otherwise → standalone.
    """
    if not ctx.last_query and not ctx.active_entities and not ctx.active_collections:
        return False

    # Rule 2: explicit anaphoric markers
    for pat in _ENTITY_PATTERNS + _TIME_PATTERNS + _METRIC_PATTERNS:
        if pat.search(query):
            return True

    # Rule 3: topic-token overlap (prefix match handles plurals/singulars)
    q_tokens = _overlap_tokens(query)
    if not q_tokens:
        return False

    ctx_text = " ".join(
        ctx.active_entities
        + [c.replace("_", " ") for c in ctx.active_collections]
        + ([ctx.last_query] if ctx.last_query else [])
    )
    ctx_tokens = _overlap_tokens(ctx_text)

    q_prefixes = {t[:5] for t in q_tokens}
    ctx_prefixes = {t[:5] for t in ctx_tokens}

    return bool(q_prefixes & ctx_prefixes)
