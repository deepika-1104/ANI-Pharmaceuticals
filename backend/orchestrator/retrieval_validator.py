"""
Retrieval Validator — scores the quality of fetched data before LLM narration.

Prevents hallucination by:
  1. Confirming at least some documents were returned
  2. Scoring keyword overlap between query terms and fetched document text
  3. Producing a confidence score [0.0, 1.0]
  4. Recommending one of: "proceed", "low_confidence", "no_data"

The recommendation drives query_orchestrator behavior:
  - "proceed"        → normal LLM narration with full system prompt
  - "low_confidence" → LLM narration with a caveat injected in system prompt
  - "no_data"        → skip LLM narration, return polite no-data message
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("voxa.orchestrator.validator")

_STOP = {
    "the", "a", "an", "of", "in", "on", "at", "by", "for", "with",
    "and", "or", "is", "are", "was", "were", "be", "been", "have",
    "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "must", "can",
    "i", "me", "my", "we", "us", "our", "you", "your", "they",
    "them", "their", "it", "its", "he", "she", "him", "her",
    "that", "this", "these", "those", "who", "what", "how", "when",
    "where", "why",
    "show", "give", "tell", "find", "list", "get", "make", "take",
    "see", "know", "like", "just", "need", "want", "help", "use",
    "data", "record", "records", "details", "please",
}

# Minimum overlap ratio to consider retrieval successful
_PROCEED_THRESHOLD = 0.25
# Minimum overlap ratio to avoid the "no_data" path when docs exist
_MIN_THRESHOLD = 0.05


@dataclass
class ValidationResult:
    """Quality assessment of one retrieval cycle."""
    is_valid: bool
    confidence: float               # 0.0–1.0
    source: str                     # "mongodb_keyword" | "mongodb_vector" | "fallback_sample" | "none"
    doc_count: int
    recommendation: str             # "proceed" | "low_confidence" | "no_data"
    reason: str
    matched_terms: list[str]        # which query terms appeared in fetched docs
    total_terms: int


def _query_terms(query: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
    return {t for t in tokens if len(t) > 2 and t not in _STOP}


def _doc_text(fetched: dict) -> str:
    """Flatten all field values from fetched docs into one searchable blob.

    Collection names are intentionally excluded — a match on the collection name
    alone (e.g. query 'patients' matching collection 'patients') is not evidence
    that the returned records answer the question. Only actual field values count.
    """
    parts: list[str] = []
    for payload in fetched.values():
        for doc in payload.get("samples", []):
            for v in doc.values():
                if isinstance(v, str):
                    parts.append(v.lower())
                elif isinstance(v, (int, float)):
                    parts.append(str(v))
    return " ".join(parts)


def validate_retrieval(
    query: str,
    fetched: dict,
    used_vector_search: bool = False,
    query_meta: Optional[object] = None,  # QueryMeta, avoids circular import
) -> ValidationResult:
    """
    Assess retrieval quality for *query* against *fetched* data.

    Parameters
    ----------
    query : str
        The (resolved) user query.
    fetched : dict
        Dict from the orchestrator: {collection_name: {"samples": [...], "total_count": int}}.
    used_vector_search : bool
        True if MongoDB Atlas vector search was used (signals higher precision).
    query_meta : QueryMeta | None
        Optional structured metadata; if provided, its entities/metrics enrich scoring.
    """
    total_docs = sum(len(p.get("samples", [])) for p in fetched.values())

    if total_docs == 0:
        logger.info("[VALIDATOR] no_data — zero documents returned")
        return ValidationResult(
            is_valid=False,
            confidence=0.0,
            source="none",
            doc_count=0,
            recommendation="no_data",
            reason="No documents returned from any selected collection",
            matched_terms=[],
            total_terms=0,
        )

    # Combine query keywords with any structured metadata hints
    query_terms = _query_terms(query)
    if query_meta is not None:
        try:
            hints = set(query_meta.search_hints())
            query_terms |= hints
        except Exception:
            pass

    if not query_terms:
        source = "mongodb_vector" if used_vector_search else "fallback_sample"
        logger.info(
            "[VALIDATOR] no scoreable terms — %d docs (%s), cannot validate relevance",
            total_docs, source,
        )
        return ValidationResult(
            is_valid=True,
            confidence=0.35,
            source=source,
            doc_count=total_docs,
            recommendation="low_confidence",
            reason="No scoreable query terms — relevance cannot be verified; applying caution",
            matched_terms=[],
            total_terms=0,
        )

    doc_text = _doc_text(fetched)
    matched = [t for t in query_terms if t in doc_text]
    overlap_ratio = len(matched) / len(query_terms)

    # Base confidence from keyword overlap
    confidence = 0.10 + (overlap_ratio * 0.80)

    # Boost for vector search (assumes higher-precision results)
    if used_vector_search:
        confidence = min(confidence + 0.10, 0.95)

    # Boost for large result sets (more docs = more likely the right collection)
    if total_docs >= 10:
        confidence = min(confidence + 0.05, 0.95)

    confidence = round(confidence, 3)
    source = "mongodb_vector" if used_vector_search else "mongodb_keyword"

    if overlap_ratio >= _PROCEED_THRESHOLD:
        recommendation = "proceed"
        is_valid = True
        reason = (
            f"Keyword overlap {overlap_ratio:.0%} ({len(matched)}/{len(query_terms)} terms), "
            f"{total_docs} docs"
        )
    elif overlap_ratio >= _MIN_THRESHOLD:
        recommendation = "low_confidence"
        is_valid = True
        reason = (
            f"Low keyword overlap {overlap_ratio:.0%} ({len(matched)}/{len(query_terms)} terms), "
            f"{total_docs} docs — proceeding with caveat"
        )
    else:
        # Docs exist but no keyword match — wrong collection or very generic query
        recommendation = "low_confidence"
        is_valid = True
        confidence = max(confidence, 0.15)
        reason = (
            f"No keyword overlap but {total_docs} docs returned — "
            "collection may be tangentially related"
        )

    logger.info(
        "[VALIDATOR] recommendation=%s confidence=%.2f overlap=%.0f%% "
        "matched=%s/%s docs=%d source=%s",
        recommendation,
        confidence,
        overlap_ratio * 100,
        len(matched),
        len(query_terms),
        total_docs,
        source,
    )

    return ValidationResult(
        is_valid=is_valid,
        confidence=confidence,
        source=source,
        doc_count=total_docs,
        recommendation=recommendation,
        reason=reason,
        matched_terms=matched,
        total_terms=len(query_terms),
    )
