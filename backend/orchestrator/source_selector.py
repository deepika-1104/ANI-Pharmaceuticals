"""
Context source selector — decides whether to answer from uploaded documents (RAG),
from MongoDB structured data (DB), both, or neither.

Called after both RAG retrieval and DB fetch have completed (parallel, zero added latency).

Decision matrix
---------------
RAG confidence  │ DB validation   │ Decision
────────────────┼─────────────────┼──────────────────────────────────────────────
HIGH (≥ thresh) │ proceed         │ merged   — both sources are relevant, include both
HIGH (≥ thresh) │ low_confidence  │ rag_only — DB data is noisy/irrelevant; docs have the answer
HIGH (≥ thresh) │ no_data         │ rag_only — DB returned nothing; docs have the answer
LOW / none      │ proceed         │ db_only  — DB data is relevant; RAG chunks are weak
LOW / none      │ low_confidence  │ rag_only — RAG is the better of two weak sources
LOW / none      │ no_data         │ rag_only — RAG is all we have (if chunks exist)
no chunks       │ proceed         │ db_only  — no document context at all
no chunks       │ low_confidence  │ none     — no good source anywhere
no chunks       │ no_data         │ none     — no data anywhere

RAG confidence definition
--------------------------
For vector search: cosine similarity score (0–1) returned by Atlas $vectorSearch.
For keyword search: token-overlap fraction (0–1) computed in the retriever.
compute_rag_confidence() takes max over all returned chunks — if the single best chunk
scores above the threshold, the documents are considered authoritative.
"""

from __future__ import annotations

import logging
from typing import Literal

from orchestrator.retrieval_validator import ValidationResult

logger = logging.getLogger("voxa.orchestrator.source_selector")

ContextSource = Literal["rag_only", "db_only", "merged", "none"]


def compute_rag_confidence(chunks: list[dict]) -> float:
    """Return the highest score among retrieved chunks; 0.0 if no chunks."""
    if not chunks:
        return 0.0
    return max(c.get("score", 0.0) for c in chunks)


def select_context_source(
    rag_chunks: list[dict],
    db_validation: ValidationResult,
    threshold: float = 0.5,
) -> ContextSource:
    """
    Pick the context source for LLM narration.

    Parameters
    ----------
    rag_chunks   : chunks returned by retrieve_chunks() — may be empty
    db_validation: ValidationResult from validate_retrieval() on MongoDB data
    threshold    : minimum RAG score to treat document retrieval as authoritative
    """
    rag_confidence = compute_rag_confidence(rag_chunks)
    rag_high = bool(rag_chunks) and rag_confidence >= threshold
    db_good  = db_validation.recommendation == "proceed"

    if not rag_chunks and db_validation.recommendation == "no_data":
        result = "none"
    elif not rag_chunks and not db_good:
        result = "none"
    elif not rag_chunks:
        result = "db_only"
    elif rag_high and db_good:
        result = "merged"
    elif rag_high:
        result = "rag_only"
    elif db_good:
        result = "db_only"
    else:
        # Low-confidence RAG + low-confidence DB: prefer RAG since it comes from
        # the user's own uploaded documents rather than unrelated structured records.
        result = "rag_only"

    logger.info(
        "[SOURCE SELECTOR] decision=%s rag_chunks=%d rag_conf=%.3f db=%s",
        result, len(rag_chunks), rag_confidence, db_validation.recommendation,
    )
    return result
