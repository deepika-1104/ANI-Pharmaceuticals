"""
Collection selector for database-backed questions.

The LLM is useful for semantic routing, but it should not be the only path
between a user question and the database. This module first builds a local
relevance score from collection names, fields, and sample values, then merges
that with the LLM's selection when the provider is available.
"""

import logging
import re

from llm.client import LLMClient

logger = logging.getLogger("voxa.orchestrator.selector")

_SELECTION_SYSTEM = """\
You are a database routing assistant. Given a user question and a list of MongoDB collections \
with their field names, return the names of the 1-4 collections MOST LIKELY to contain the data \
needed to answer the question.

IMPORTANT: Use the EXACT collection names from the catalog below — do not invent or shorten names.

Rules:
- Return ONLY a comma-separated list of collection names (exactly as they appear in the catalog).
- Choose at most 4 collections.
- If none look relevant, return an empty response.

Domain routing — use the catalog field list to find the right collection:
- Patient diseases, diagnoses, medical conditions (diabetes, hypertension, cancer, etc.) \
→ pick the collection that has a 'diagnosis' field (NOT the patient demographics collection)
- Doctor details, physician profiles, active doctors, doctor count, specialisation, years of experience \
→ pick the collection with 'specialization' or 'years_experience' fields (NOT the patients collection)
- Hospital capacity, ICU beds, ER beds, total beds → pick the collection with 'icu_beds' or 'total_beds' fields
- Drug catalogue, drug names, pharmaceutical products, medicines manufactured \
→ pick the collection with 'drug_name' or 'category' fields (NOT the prescriptions collection)
- Drug prescriptions, medications given to patients, dosage → pick the collection with 'dosage' or 'drug_id' fields
- Lab tests, test results, blood work → pick the collection with 'test_name' or 'result' fields
- Bills, payments, insurance claims → pick the collection with 'total_amount' or 'payment_method' fields
- Production efficiency, shift output, energy usage, operations by production line, breakdown of operations → pick the collection with 'efficiency', 'units_produced', or 'production_line' fields
- Machine maintenance, repair, downtime → pick the collection with 'downtime_hours' or 'maintenance_type' fields
- Quality inspections, defect rates, QC scores → pick the collection with 'inspection_type' or 'deviations_found' fields
- Inventory, stock, raw materials, expiry → pick the collection with 'movement_type' or 'batch_number' fields
- Employee records, salaries, departments → pick the collection with 'department' or 'salary' fields
- Audit trail, access logs, compliance → pick the collection with 'action' and 'entity_type' fields

CRITICAL DISAMBIGUATION — these rules OVERRIDE everything above:
- Query mentions "doctor", "doctors", "physician", or "physicians" → NEVER select the patients collection.
- Query mentions "patient" or "patients" (not in compound like "patient_id in billing") → NEVER select the doctors/physicians collection.
- Query mentions "drug", "drugs", "medicine", "medicines", "medication", "medications", \
"pharmaceutical", or "pharmaceuticals" as the subject → pick the collection with 'drug_name' or \
'category' fields. NEVER select the prescriptions collection for the drug catalog.
- Query mentions "employee", "employees", "staff", "workforce", "workers", "worker", \
"personnel", or "headcount" → select the employees collection (has 'department' or 'salary' fields). \
NEVER select patients for these terms.
- Query mentions "machine", "machines", "equipment", or "machinery" → select the machinery \
collection (has 'downtime_hours' or 'maintenance_type' fields).
- Always choose the collection whose name directly matches the primary entity in the question.
"""

_STOP_WORDS = {
    # Articles / prepositions / conjunctions
    "the", "a", "an", "of", "in", "on", "at", "by", "for", "with",
    "and", "or", "not", "to", "from", "into", "about", "over", "after",
    "before", "above", "below", "around", "through", "under", "since",
    "both", "between", "such", "than", "then", "also", "only",
    # Auxiliary / modal verbs
    "is", "are", "was", "were", "be", "been", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "shall", "must", "can",
    # Pronouns / determiners
    "i", "me", "my", "we", "us", "our", "you", "your", "they",
    "them", "their", "it", "its", "he", "she", "him", "her",
    "that", "this", "these", "those", "who", "whom", "which",
    # Question words
    "what", "how", "when", "where", "why",
    # Generic action / filler verbs
    "show", "give", "tell", "find", "list", "get", "make", "take",
    "come", "see", "know", "like", "just", "need", "want", "help",
    "use", "back", "here", "there", "well", "still", "very", "good",
    "great", "per", "each", "many", "much", "more", "most", "any",
    "some", "all", "few",
    # Meta / dataset words (too generic for routing)
    "data", "dataset", "record", "records", "details", "please",
    # Greetings — must never influence collection scoring
    "hello", "hi", "hey", "howdy", "greetings", "hear", "heard",
    "thanks", "thank", "okay", "sure", "yes", "yeah",
    "alright", "ok", "got", "understood", "fine", "bye", "goodbye",
}


# Maps query words to additional collection-matching terms.
# Handles semantic gaps where heuristic scoring fails because the query uses
# a synonym that doesn't appear in any collection name or field list.
_QUERY_SYNONYMS: dict[str, list[str]] = {
    # Equipment / Machinery
    "machine": ["machinery"],
    "machines": ["machinery"],
    "equipment": ["machinery"],
    "equipments": ["machinery"],
    # Staff / Employees
    "staff": ["employee", "employees"],
    "workforce": ["employee", "employees"],
    "workers": ["employee", "employees"],
    "worker": ["employee", "employees"],
    "personnel": ["employee", "employees"],
    "headcount": ["employee", "employees"],
    # Pharmaceuticals / Drugs
    "medicine": ["drug", "pharmaceutical"],
    "medicines": ["drug", "pharmaceutical"],
    "pharmaceutical": ["drug"],
    "pharmaceuticals": ["drug"],
    "medication": ["drug"],
    "medications": ["drug"],
    # Medical condition synonyms
    "sugar": ["diabetes", "glucose", "antidiabetic"],
    "thinners": ["anticoagulant"],
    "thinner": ["anticoagulant"],
    "breathing": ["respiratory", "pulmonary"],
}


def _terms(query: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
    base = [t for t in tokens if len(t) > 2 and t not in _STOP_WORDS]
    expanded: list[str] = []
    for t in base:
        expanded.append(t)
        for synonym in _QUERY_SYNONYMS.get(t, []):
            if synonym not in expanded:
                expanded.append(synonym)
    return expanded


# Pairs of (query_terms_that_indicate_entity, collection_name_substring_to_exclude).
# When any query term from the first set appears, collections whose name contains
# the exclusion substring are penalised heavily so they cannot win.
_CROSS_ENTITY_EXCLUSIONS: list[tuple[frozenset[str], str]] = [
    (frozenset({"doctor", "doctors", "physician", "physicians"}), "patient"),
    (frozenset({"patient", "patients"}), "doctor"),
    (frozenset({"patient", "patients"}), "physician"),
    (frozenset({"employee", "employees", "staff", "worker", "workers",
                "workforce", "personnel", "headcount"}), "patient"),
    (frozenset({"machine", "machines", "equipment", "machinery"}), "patient"),
]


def _heuristic_scores(
    query: str,
    collection_metadata: dict[str, dict],
) -> list[tuple[str, int]]:
    terms = _terms(query)
    if not terms:
        return []

    # Determine which collection name substrings are excluded for this query
    excluded_name_substrings: list[str] = []
    for query_signals, exclude_substr in _CROSS_ENTITY_EXCLUSIONS:
        if any(t in query_signals for t in terms):
            excluded_name_substrings.append(exclude_substr)

    scored: list[tuple[str, int]] = []
    for name, meta in collection_metadata.items():
        name_text = name.lower().replace("_", " ")
        fields = meta.get("fields", [])
        searchable = " ".join(
            [
                name_text,
                " ".join(fields),
                " ".join(meta.get("searchable_fields", [])),
                str(meta.get("sample_text", "")),
            ]
        ).lower()

        score = 0
        for term in terms:
            if term in name_text:
                score += 8
            if any(term in field.lower() for field in fields):
                score += 4
            if term in searchable:
                score += 2

        # Apply cross-entity exclusion penalty
        if any(excl in name_text for excl in excluded_name_substrings):
            score -= 1000

        if score > 0:
            scored.append((name, score))

    return sorted(scored, key=lambda item: item[1], reverse=True)


def build_catalog_text(collection_metadata: dict[str, dict]) -> str:
    """Format collection metadata into a readable catalog for the LLM."""
    lines = []
    for name, meta in collection_metadata.items():
        fields = meta.get("fields", [])
        count = meta.get("doc_count", "?")
        field_str = ", ".join(fields[:12]) if fields else "unknown"
        lines.append(f"- {name} ({count} docs): [{field_str}]")
    return "\n".join(lines)


async def select_collections(
    query: str,
    collection_metadata: dict[str, dict],
    llm: LLMClient,
    max_collections: int = 4,
) -> list[str]:
    """
    Pick relevant collections for *query*.

    Local scoring is always available. LLM routing is merged in when it works,
    and the final fallback is top collections by document count.
    """
    if not collection_metadata:
        return []

    heuristic = _heuristic_scores(query, collection_metadata)
    heuristic_names = [name for name, _ in heuristic[:max_collections]]

    catalog = build_catalog_text(collection_metadata)
    messages = [
        {"role": "system", "content": _SELECTION_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Available collections:\n{catalog}\n\n"
                f"User question: {query}\n\n"
                f"Which collections should I query? (comma-separated list)"
            ),
        },
    ]

    try:
        raw = llm.complete(messages).strip()
        chosen = [c.strip().lower() for c in raw.split(",") if c.strip()]
        valid = [c for c in chosen if c in collection_metadata]

        merged: list[str] = []
        for name in valid + heuristic_names:
            if name not in merged:
                merged.append(name)
        if merged:
            selected = merged[:max_collections]
            logger.info(f"Selected collections: {selected}")
            return selected
    except Exception as exc:
        logger.warning(f"LLM collection selection failed: {exc}")

    if heuristic_names:
        logger.info(f"Heuristic collection selection: {heuristic_names}")
        return heuristic_names

    if _terms(query):
        logger.info("No relevant collections matched the request")
        return []

    sorted_by_docs = sorted(
        collection_metadata.keys(),
        key=lambda n: collection_metadata[n].get("doc_count", 0),
        reverse=True,
    )
    fallback = sorted_by_docs[:max_collections]
    logger.info(f"Fallback collection selection: {fallback}")
    return fallback
