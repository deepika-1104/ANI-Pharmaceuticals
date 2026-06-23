"""Base identity and guardrails — single source of truth for top-level prompt content."""
from config.settings import SYSTEM_PROMPT as BASE_IDENTITY, LLM_GUARDRAILS as _cfg_guardrails

# Fall back to a minimal set so an empty config never strips all safety instructions.
_FALLBACK_GUARDRAILS = [
    "Only state facts, figures, and names that appear explicitly in the provided data context.",
    "If the data does not contain enough information to answer the question, say so clearly.",
    "Do not fabricate, estimate, or infer values that are not present in the data.",
]
GUARDRAILS = _cfg_guardrails if _cfg_guardrails else _FALLBACK_GUARDRAILS

LOW_CONFIDENCE_CAVEAT = (
    "IMPORTANT — DATA CONFIDENCE IS LOW:\n"
    "The retrieved data may only be partially relevant to this query. "
    "You MUST apply these rules:\n"
    "- Do not state any specific figure, name, or fact as certain unless it appears "
    "verbatim in the DATA CONTEXT above.\n"
    "- If you are uncertain whether a value answers the user's question, say so explicitly "
    "('the available data shows X, but this may not fully reflect your query').\n"
    "- Do not synthesise or combine values from different records to produce a new number.\n"
    "- If the data clearly does not answer the question, say the information was not found "
    "rather than approximating from what is available."
)
