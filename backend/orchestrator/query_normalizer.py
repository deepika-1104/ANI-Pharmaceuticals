"""
Query Normalizer — converts natural language into structured query metadata.

Extracts:
  - metrics     : measurable NUMERIC values requested (e.g. "total_amount", "score")
  - entities    : named things the query is about (people, places, products)
  - filters     : key→value conditions to apply (e.g. {"status": "active"})
  - aggregations: operations like count, sum, avg, max, min, group_by
  - time_range  : temporal scope as a string (e.g. "this month", "2024")
  - grouping    : field to group results by (e.g. "region", "gender", "status")

The extracted metadata is used downstream to:
  1. Build better MongoDB search queries
  2. Guide collection selection
  3. Inject structured context into the LLM system prompt
  4. Populate the standardised API response metadata
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional
import re
from llm.client import LLMClient

logger = logging.getLogger("voxa.orchestrator.normalizer")

_SYSTEM = """\
You are a query metadata extractor for an enterprise analytics platform.
Given a user query, extract structured information and return ONLY valid JSON.

Return a JSON object with these exact fields:
  "metrics"      : list of measurable NUMERIC field names (snake_case strings)
  "entities"     : list of named entities mentioned (people, places, categories)
  "filters"      : dict of field→value constraints
  "aggregations" : list of operations: "count", "sum", "avg", "max", "min", "group_by"
  "time_range"   : time period as a string, or null
  "grouping"     : field name to group/distribute results by, or null

═══ CRITICAL RULES ═══

RULE 1 — GROUP_BY vs FILTER (most important):
  • When the query uses "vs", "versus", "compared to", or lists MULTIPLE VALUES of the
    same field to count/compare (e.g. "male, female, other", "paid vs partial",
    "completed vs cancelled", "passed, failed, under review", "active vs inactive",
    "each specialization", "by region", "breakdown", "distribution"):
      → set grouping = that field name
      → include "count" AND "group_by" in aggregations
      → do NOT put those values in filters — even when only two values are named
      CRITICAL: "completed vs cancelled", "active vs inactive", "paid vs unpaid" etc.
      must ALL use grouping, never filters. Never produce filters like
      {"status": "completed,cancelled"} — that is always wrong.

  • When the query asks about ONE specific value only (e.g. "how many active patients",
    "how many cancelled appointments"):
      → set filters = {"status": "active"}, aggregations = ["count"]
      → grouping = null

RULE 2 — METRICS must be NUMERIC fields only:
  NEVER put ID fields ("bill_id", "patient_id", "record_id", "appointment_id",
  "doctor_id", "inspection_id", etc.) in metrics — they are strings, not numbers.
  Good metrics: "total_amount", "score", "daily_capacity_units", "consultation_fee",
                "bed_capacity", "coverage_percentage", "deductible_usd", "age"
  Bad metrics:  "bill_id", "patient_id", "record_id" (these are IDs, not numbers)

RULE 3 — COMPOUND QUERIES:
  When the query asks for multiple things, capture ALL of them.
  "total amount AND breakdown by status" → metrics:["total_amount"],
  aggregations:["sum","count","group_by"], grouping:"status"

RULE 4 — MAX/MIN without restrictive filters:
  "which has highest/lowest X" → aggregations:["max"/"min"], metrics:["x_field"]
  Only add a filter if the user EXPLICITLY says "among active ones" or similar.
  Do NOT add a filter just because the query also mentions a category.

RULE 5 — AVG always pairs with a numeric metric field name.

═══ EXAMPLES ═══

"How many male, female, and other patients do we have?"
→ {"metrics":[],"entities":["patients"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"gender"}

"What is the total billing amount and how many bills are Paid vs Partial?"
→ {"metrics":["total_amount"],"entities":["billing"],"filters":{},"aggregations":["sum","count","group_by"],"time_range":null,"grouping":"status"}

"How many quality inspections passed, failed, or are under review? What is the average score?"
→ {"metrics":["score"],"entities":["quality_inspections"],"filters":{},"aggregations":["count","group_by","avg"],"time_range":null,"grouping":"status"}

"Give me exact count of passed quality inspections"
→ {"metrics":[],"entities":["quality_inspections"],"filters":{"status":"passed"},"aggregations":["count"],"time_range":null,"grouping":null}

"Which production line has the highest daily capacity?"
→ {"metrics":["daily_capacity_units"],"entities":["production_lines"],"filters":{},"aggregations":["max"],"time_range":null,"grouping":null}

"Which specialization has the most doctors? Show top 5."
→ {"metrics":[],"entities":["doctors"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"specialization"}

"Compare all insurance providers by coverage percentage and deductible"
→ {"metrics":["coverage_percentage","deductible_usd"],"entities":["insurance_providers"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"plan_type"}

"How many diabetic patients by region this month?"
→ {"metrics":["patient_count"],"entities":["patients"],"filters":{"condition":"diabetes"},"aggregations":["count","group_by"],"time_range":"this month","grouping":"region"}

"Show me active patients"
→ {"metrics":[],"entities":["patients"],"filters":{"status":"active"},"aggregations":["count"],"time_range":null,"grouping":null}

"What is the average consultation fee for cardiologists?"
→ {"metrics":["consultation_fee"],"entities":["doctors"],"filters":{"specialization":"cardiology"},"aggregations":["avg"],"time_range":null,"grouping":null}

"Who are the top 5 most experienced doctors?"
→ {"metrics":["years_experience"],"entities":["doctors"],"filters":{},"aggregations":["max"],"time_range":null,"grouping":null}

"How many lab results are flagged as Abnormal?"
→ {"metrics":[],"entities":["lab_results"],"filters":{"status":"Abnormal"},"aggregations":["count"],"time_range":null,"grouping":null}

"Give me an overview of all our regions — how many hospitals and plants does each one have?"
→ {"metrics":["hospitals_count","plants_count"],"entities":["regions"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"region_name"}

"What is the appointment status breakdown?"
→ {"metrics":[],"entities":["appointments"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"status"}

"Compare completed vs cancelled appointments"
→ {"metrics":[],"entities":["appointments"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"status"}

"Completed appointments vs no-show"
→ {"metrics":[],"entities":["appointments"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"status"}

"Active vs inactive patients"
→ {"metrics":[],"entities":["patients"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"is_active"}

"What is the prescription status breakdown?"
→ {"metrics":[],"entities":["prescriptions"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"status"}

"What are the top 5 diagnoses?"
→ {"metrics":[],"entities":["medical_records"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"diagnosis"}

"How many patients have blood type O+?"
→ {"metrics":[],"entities":["patients"],"filters":{"blood_type":"O+"},"aggregations":["count"],"time_range":null,"grouping":null}

"List all hospitals with their city, state, and bed capacity"
→ {"metrics":["bed_capacity"],"entities":["hospitals"],"filters":{},"aggregations":[],"time_range":null,"grouping":null}

"List all cardiovascular drugs in our catalog"
→ {"metrics":[],"entities":["drug_catalog"],"filters":{"category":"cardiovascular"},"aggregations":[],"time_range":null,"grouping":null}

"Which hospital has the highest number of appointments?"
→ {"metrics":[],"entities":["appointments"],"filters":{},"aggregations":["count","group_by","max"],"time_range":null,"grouping":"hospital_id"}

"Billing Summary Across All Bills"
→ {"metrics":["total_amount","insurance_covered","patient_due"],"entities":["billing"],"filters":{},"aggregations":["sum","avg","count","group_by"],"time_range":null,"grouping":"status"}

"How many employees are in each department?"
→ {"metrics":[],"entities":["employees"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"department"}

"What is the quality inspection pass rate?"
→ {"metrics":["score"],"entities":["quality_inspections"],"filters":{},"aggregations":["count","group_by","avg"],"time_range":null,"grouping":"status"}

"What is the pass/fail rate for inspections?"
→ {"metrics":[],"entities":["quality_inspections"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"status"}

"What machinery is currently under maintenance?"
→ {"metrics":[],"entities":["machinery"],"filters":{"status":"maintenance"},"aggregations":[],"time_range":null,"grouping":null}

"How many machines are under maintenance?"
→ {"metrics":[],"entities":["machinery"],"filters":{"status":"maintenance"},"aggregations":["count"],"time_range":null,"grouping":null}

"Show me all doctors with their specializations"
→ {"metrics":[],"entities":["doctors"],"filters":{},"aggregations":[],"time_range":null,"grouping":null}

"List all patients and their hospital"
→ {"metrics":[],"entities":["patients"],"filters":{},"aggregations":[],"time_range":null,"grouping":null}

"Give me an overview of operations — total counts and status breakdown"
→ {"metrics":[],"entities":["operations","machinery","quality_inspections"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"status"}

"What is the breakdown of operations by production line?"
→ {"metrics":[],"entities":["operations"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"production_line"}

"Show operations breakdown by status"
→ {"metrics":[],"entities":["operations"],"filters":{},"aggregations":["count","group_by"],"time_range":null,"grouping":"status"}

"How many prescriptions are currently active?"
→ {"metrics":[],"entities":["prescriptions"],"filters":{"status":"active"},"aggregations":["count"],"time_range":null,"grouping":null}

"How many active prescriptions are there?"
→ {"metrics":[],"entities":["prescriptions"],"filters":{"status":"active"},"aggregations":["count"],"time_range":null,"grouping":null}

"Show employee headcount"
→ {"metrics":[],"entities":["employees"],"filters":{},"aggregations":["count"],"time_range":null,"grouping":null}

"What is the total employee headcount?"
→ {"metrics":[],"entities":["employees"],"filters":{},"aggregations":["count"],"time_range":null,"grouping":null}

"Which suppliers have the highest ratings?"
→ {"metrics":["rating"],"entities":["suppliers"],"filters":{},"aggregations":["max"],"time_range":null,"grouping":null}

"Which supplier has the best performance?"
→ {"metrics":["rating","performance_score"],"entities":["suppliers"],"filters":{},"aggregations":["max"],"time_range":null,"grouping":null}

"Based on current maintenance data, which machines are most at risk?"
→ {"metrics":["downtime_hours"],"entities":["machinery"],"filters":{"status":"maintenance"},"aggregations":["max","count"],"time_range":null,"grouping":null}

"Which machines require the most maintenance?"
→ {"metrics":["downtime_hours"],"entities":["machinery"],"filters":{},"aggregations":["max"],"time_range":null,"grouping":null}

"How many active doctors are in our network?"
→ {"metrics":[],"entities":["doctors"],"filters":{"status":"active"},"aggregations":["count"],"time_range":null,"grouping":null}
"""


_TOP_N_RE = re.compile(
    r'\b(?:top|first|leading)\s+(\d+)\b|\bbottom\s+(\d+)\b|\blast\s+(\d+)\b',
    re.IGNORECASE,
)


def _extract_top_n(query: str) -> int:
    """Return the N in 'top N' / 'bottom N' queries, capped at 100. Defaults to 5."""
    m = _TOP_N_RE.search(query)
    if m:
        n_str = next(g for g in m.groups() if g is not None)
        return min(int(n_str), 100)
    return 5


@dataclass
class QueryMeta:
    """Structured metadata extracted from a natural language query."""
    metrics: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    aggregations: list[str] = field(default_factory=list)
    time_range: Optional[str] = None
    grouping: Optional[str] = None
    top_n: int = 5
    raw_query: str = ""

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics,
            "entities": self.entities,
            "filters": self.filters,
            "aggregations": self.aggregations,
            "time_range": self.time_range,
            "grouping": self.grouping,
            "top_n": self.top_n,
        }

    def is_empty(self) -> bool:
        return not (self.metrics or self.entities or self.filters)

    def search_hints(self) -> list[str]:
        """Return flat list of terms useful for keyword search augmentation."""
        hints: list[str] = []
        hints.extend(self.metrics)
        hints.extend(self.entities)
        hints.extend(str(v) for v in self.filters.values() if isinstance(v, str))
        if self.grouping:
            hints.append(self.grouping)
        return [h.lower() for h in hints if h and isinstance(h, str)]


async def normalize_query(query: str, llm: LLMClient) -> QueryMeta:
    """
    Extract structured metadata from *query*.

    Returns an empty QueryMeta on any failure — the pipeline continues
    without structured metadata rather than failing entirely.
    """
    try:
        raw = llm.complete(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": query},
            ],
            json_mode=True,
        )
        # complete() may return str or dict depending on json_mode support
        if isinstance(raw, str):
            import json as _json
            try:
                data = _json.loads(raw)
            except Exception:
                # Try extracting JSON from text
                import re
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                data = _json.loads(m.group(0)) if m else {}
        else:
            data = raw or {}

        # Sanitize metrics: strip out obvious ID/string fields
        _ID_SUFFIXES = ("_id", "_number", "_code", "_key", "id")
        raw_metrics = data.get("metrics") or []
        clean_metrics = [
            m for m in raw_metrics
            if isinstance(m, str)
            and not any(m.lower().endswith(s) for s in _ID_SUFFIXES)
            and m.lower() not in ("id", "key", "code")
        ]

        raw_entities = data.get("entities") or []
        clean_entities = [e for e in raw_entities if isinstance(e, str)]

        meta = QueryMeta(
            metrics=clean_metrics,
            entities=clean_entities,
            filters=data.get("filters") or {},
            aggregations=data.get("aggregations") or [],
            time_range=data.get("time_range") or None,
            grouping=data.get("grouping") or None,
            top_n=_extract_top_n(query),
            raw_query=query,
        )
        logger.info(
            "[NORMALIZER] metrics=%s entities=%s filters=%s aggs=%s time=%s group=%s top_n=%d",
            meta.metrics,
            meta.entities,
            meta.filters,
            meta.aggregations,
            meta.time_range,
            meta.grouping,
            meta.top_n,
        )
        return meta
    except Exception as exc:
        logger.warning("[NORMALIZER] failed (%s) — using empty meta", exc)
        return QueryMeta(raw_query=query, top_n=_extract_top_n(query))
