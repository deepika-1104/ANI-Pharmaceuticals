"""
Semantic keyword expander.

Two modes — both are active by default and complement each other:

Mode 1 · LLM expansion (always available)
  Uses a small LLM call to derive domain synonyms, abbreviations, and
  related terms from the user query.  The expanded set is merged with
  the base keywords and passed to MongoDB regex search, dramatically
  improving recall for queries like "top performers" → ["ranking",
  "leaders", "best", "highest", "score"].

Mode 2 · Embedding vector search (optional — activate via env vars)
  If EMBEDDING_MODEL is set, encodes the query as a dense vector and
  runs MongoDB Atlas $vectorSearch on each selected collection.
  Falls back to Mode 1 silently when the index is absent or the API
  call fails.

  Required env vars to enable Mode 2:
    EMBEDDING_MODEL      e.g. "text-embedding-3-small"
    EMBEDDING_API_KEY    defaults to LLM_API_KEY
    EMBEDDING_BASE_URL   defaults to "https://api.openai.com/v1"
    EMBEDDING_FIELD      MongoDB field storing the vector (default "embedding")
    EMBEDDING_INDEX      Atlas vector index name (default "vector_index")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from llm.client import LLMClient

logger = logging.getLogger("voxa.orchestrator.semantic")

# ── Static domain synonym table ───────────────────────────────────────────────
#
# Maps layman trigger words (lowercase) to exact DB vocabulary + related terms.
# This runs BEFORE the LLM expansion so that common medical/manufacturing terms
# are always resolved — even when the LLM call is slow or rate-limited.
#
# Each value is a list of single-word search terms that regex-match the relevant
# field values in MongoDB (e.g. "diabetes" substring-matches "Type 2 Diabetes
# Mellitus", "cardiac" matches "Cardiology" and cardiac-related diagnoses).

_DOMAIN_SYNONYMS: dict[str, list[str]] = {
    # ── Medical conditions ──────────────────────────────────────────────────
    "diabetic":      ["diabetes", "mellitus", "insulin", "metformin", "antidiabetic"],
    "diabetes":      ["diabetic", "mellitus", "insulin", "metformin", "antidiabetic"],
    "sugar":         ["diabetes", "glucose", "hyperglycemia", "insulin", "mellitus"],
    "cardiac":       ["cardiology", "cardiovascular", "myocardial", "coronary", "atrial"],
    "heart":         ["cardiology", "cardiovascular", "myocardial", "coronary", "cardiac"],
    "kidney":        ["renal", "nephrology", "glomerular", "nephritis", "uremia"],
    "renal":         ["kidney", "nephrology", "glomerular", "nephritis"],
    "breathing":     ["respiratory", "pulmonary", "pneumonia", "asthma", "COPD"],
    "respiratory":   ["pulmonary", "pneumonia", "asthma", "COPD", "breathing"],
    "lung":          ["pulmonary", "respiratory", "pneumonia", "COPD", "asthma"],
    "mental":        ["psychiatric", "psychiatry", "anxiety", "depression", "psychological"],
    "psychiatric":   ["psychiatry", "anxiety", "depression", "mental", "psychological"],
    "anxiety":       ["psychiatric", "GAD", "anxiety", "psychological", "mental"],
    "cancer":        ["oncology", "tumor", "carcinoma", "malignant", "chemotherapy"],
    "oncology":      ["cancer", "tumor", "carcinoma", "malignant"],
    "bone":          ["orthopedic", "fracture", "osteoporosis", "arthritis", "rheumatology"],
    "arthritis":     ["rheumatology", "joint", "autoimmune", "inflammation"],
    "hypertension":  ["blood pressure", "cardiovascular", "antihypertensive", "systolic"],
    "neurological":  ["neurology", "seizure", "epilepsy", "stroke", "migraine"],
    "infectious":    ["infection", "sepsis", "bacteria", "antibiotic", "microbiology"],
    # ── Drugs / pharmacy ───────────────────────────────────────────────────
    "blood thinner": ["anticoagulant", "antiplatelet", "warfarin", "heparin", "clopidogrel"],
    "anticoagulant": ["warfarin", "heparin", "clopidogrel", "antiplatelet"],
    "antidiabetic":  ["metformin", "insulin", "diabetes", "hypoglycemic"],
    "medicines":     ["drugs", "medication", "pharmaceutical", "prescription"],
    "medicine":      ["drug", "medication", "pharmaceutical", "prescription"],
    "drugs":         ["medication", "pharmaceutical", "drug", "prescription", "catalog"],
    "pharmaceuticals": ["drugs", "medication", "catalog", "compound", "dosage"],
    # ── Workforce / staff ───────────────────────────────────────────────────
    "staff":         ["employees", "personnel", "workforce", "headcount"],
    "workforce":     ["employees", "personnel", "staff", "headcount"],
    "workers":       ["employees", "personnel", "staff"],
    "headcount":     ["employees", "personnel", "staff", "workforce"],
    # ── Manufacturing / equipment ───────────────────────────────────────────
    "machine":       ["machinery", "equipment", "operational", "mechanical"],
    "machines":      ["machinery", "equipment", "operational"],
    "equipment":     ["machinery", "machines", "apparatus", "device"],
    "maintenance":   ["repair", "downtime", "operational", "machinery", "logs"],
    "plant":         ["facility", "manufacturing", "production", "factory"],
    "manufacturing": ["plant", "production", "facility", "operations", "machinery"],
    # ── Finance / billing ───────────────────────────────────────────────────
    "revenue":       ["billing", "amount", "total", "payment", "invoice"],
    "invoice":       ["billing", "amount", "total", "payment", "bill"],
    "payment":       ["billing", "amount", "paid", "invoice", "financial"],
}


def _static_expand(query: str, keywords: list[str]) -> list[str]:
    """
    Inject domain synonyms for any trigger words found in the query or keyword list.
    Checks substrings so 'diabetic cases' → triggers 'diabetic' → injects diabetes terms.
    """
    text = (query + " " + " ".join(keywords)).lower()
    extra: list[str] = []
    for trigger, synonyms in _DOMAIN_SYNONYMS.items():
        if trigger in text:
            extra.extend(synonyms)
    return list(dict.fromkeys(extra))  # deduplicate, preserve order


# ── LLM expansion ─────────────────────────────────────────────────────────────

_EXPAND_SYSTEM = """\
You are a search query expander for an enterprise analytics database.
Given a user question, output ONLY a comma-separated list of 5-8 single-word
search terms — synonyms, abbreviations, and domain-specific vocabulary that
would help find relevant records.

Rules:
- Single words only (no phrases)
- Do NOT repeat words already in the query
- Do NOT output sentences or explanations
- Cover alternative phrasings and domain jargon

Example
  Input : "show me top 3 products by revenue this quarter"
  Output: sales, earnings, income, best, ranking, items, goods, turnover
"""


async def expand_keywords_llm(query: str, llm: LLMClient) -> list[str]:
    """
    Return 5-8 semantically related single-word terms for *query*.
    Returns [] on any failure so the pipeline continues unaffected.
    """
    try:
        raw = llm.complete(
            [
                {"role": "system", "content": _EXPAND_SYSTEM},
                {"role": "user", "content": query},
            ]
        )
        terms = [t.strip().lower() for t in raw.split(",") if t.strip()]
        # Keep only single tokens of useful length
        terms = [t for t in terms if " " not in t and 2 < len(t) <= 30][:8]
        logger.info("Semantic expansion: %d terms for query=%r", len(terms), query[:60])
        return terms
    except Exception as exc:
        logger.warning("LLM keyword expansion failed: %s", exc)
        return []


# ── Embedding vector search ───────────────────────────────────────────────────


def _embedding_client():
    """
    Lazily build an AsyncOpenAI client configured for embedding calls.
    Returns None when EMBEDDING_MODEL is not set.
    """
    import os
    model = os.getenv("EMBEDDING_MODEL")
    if not model:
        return None, None
    try:
        from openai import AsyncOpenAI
        api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY")
        base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
        return AsyncOpenAI(api_key=api_key, base_url=base_url), model
    except ImportError:
        logger.warning("openai package not installed — vector search disabled")
        return None, None


async def get_query_embedding(query: str) -> Optional[list[float]]:
    """
    Encode *query* as a dense vector using the configured embedding model.
    Returns None when EMBEDDING_MODEL is not set or on any error.
    """
    client, model = _embedding_client()
    if client is None:
        return None
    try:
        response = await client.embeddings.create(model=model, input=query)
        return response.data[0].embedding
    except Exception as exc:
        logger.warning("Embedding API call failed: %s", exc)
        return None


# ── Public helper ─────────────────────────────────────────────────────────────


async def build_search_terms(
    query: str,
    base_keywords: list[str],
    llm: LLMClient,
) -> list[str]:
    """
    Return the merged keyword list: base_keywords + static synonyms + LLM-expanded terms.
    Static expansion runs first so layman medical/manufacturing terms always resolve
    to exact DB vocabulary regardless of LLM availability or rate limits.
    Deduplicates and caps at 15 terms.
    """
    static_extra = _static_expand(query, base_keywords)
    if static_extra:
        logger.debug(
            "Static expansion added %d terms for query=%r: %s",
            len(static_extra), query[:60], static_extra,
        )
    expanded = await expand_keywords_llm(query, llm)
    merged = list(dict.fromkeys(base_keywords + static_extra + expanded))
    return merged[:15]
