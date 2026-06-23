"""
Common utilities shared across the backend.
"""

from typing import Any


def sanitize_doc(doc: Any) -> Any:
    """
    Recursively convert a MongoDB document to a JSON-serializable dict.
    - ObjectId  → str
    - datetime  → ISO-8601 str
    - All other types pass through unchanged.
    """
    if isinstance(doc, dict):
        return {
            k: (str(v) if k == "_id" else sanitize_doc(v))
            for k, v in doc.items()
        }
    if isinstance(doc, list):
        return [sanitize_doc(item) for item in doc]
    if hasattr(doc, "isoformat"):          # datetime / date
        return doc.isoformat()
    if hasattr(doc, "__str__") and type(doc).__module__ == "bson":
        return str(doc)                    # ObjectId and other BSON types
    return doc


def truncate_str(text: str, max_chars: int, suffix: str = "…[truncated]") -> str:
    """Return *text* truncated to *max_chars* characters."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + suffix
