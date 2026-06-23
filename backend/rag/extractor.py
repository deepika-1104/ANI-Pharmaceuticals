"""
Text extractor — pulls plain text from uploaded file bytes.

Returns (text, ChunkStrategy) so the chunker knows the right splitting approach
for each file type. Strategy is declared here because the extractor already knows
the content type — no separate dispatch layer needed.

Supported types:
  .txt / .md  → SECTION         (paragraph-aware; blank-line boundaries)
  .pdf        → SECTION         (requires pypdf; splits on page breaks + paragraphs)
  .docx       → SECTION         (requires python-docx; split on paragraph breaks)
  .csv        → ROW             (each data row becomes one chunk)
  .json       → JSON_RECORD     (each top-level object/item becomes one chunk)
"""

import asyncio
import io
import json
import logging
from enum import Enum
from pathlib import Path

logger = logging.getLogger("voxa.rag.extractor")


class ChunkStrategy(str, Enum):
    SLIDING_WINDOW = "sliding_window"  # fallback for oversized sections
    SECTION        = "section"         # TXT, MD, PDF, DOCX — paragraph/blank-line boundaries
    ROW            = "row"             # CSV  — one row = one chunk
    JSON_RECORD    = "json_record"     # JSON — one record = one chunk
    IMAGE          = "image"           # image files — vision LLM description as chunk(s)


# Image extensions handled by extract_image() — imported by indexer.py
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})

_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png",  ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp",
}

_REFUSAL_PHRASES = ("i cannot", "i'm unable", "i can't describe", "i am not able")


def _resize_image(image_bytes: bytes, max_px: int = 1024) -> bytes:
    """
    Downscale image so its longest edge is at most max_px pixels.
    Never upscales. Converts RGBA/P images to RGB before JPEG save to avoid
    'cannot write mode RGBA as JPEG' errors.
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow is not installed. Run: pip install Pillow")
    img = Image.open(io.BytesIO(image_bytes))
    fmt = img.format or "PNG"
    if max(img.width, img.height) > max_px:
        img.thumbnail((max_px, max_px), Image.LANCZOS)
    if fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


async def extract_image(
    file_bytes: bytes,
    filename: str,
    storage_key: str,
) -> tuple[str, ChunkStrategy, dict]:
    """
    Describe an image via the vision LLM.

    Returns (description_text, ChunkStrategy.IMAGE, image_metadata_dict).
    Retries once with a medical/clinical prompt on safety refusal.
    Raises ValueError if the model refuses after retry or returns < 50 chars.
    """
    from llm.client import get_llm_client
    from config.settings import VISION_MODEL, PRIMARY_MODEL
    from prompts.vision import VISION_PROMPT_DEFAULT, VISION_PROMPT_MEDICAL

    if not VISION_MODEL:
        raise ValueError(
            "VISION_MODEL is not configured. Set it in backend/.env "
            "(e.g. VISION_MODEL=llama-3.2-11b-vision-preview for Groq)."
        )

    ext = Path(filename).suffix.lower()
    media_type = _MEDIA_TYPES.get(ext, "image/jpeg")
    resized = _resize_image(file_bytes)
    llm = get_llm_client()

    description = await llm.complete_vision(
        prompt=VISION_PROMPT_DEFAULT,
        image_bytes=resized,
        media_type=media_type,
    )

    if any(p in description.lower() for p in _REFUSAL_PHRASES):
        logger.info("[EXTRACTOR] vision refusal on default prompt — retrying with medical framing: %s", filename)
        await asyncio.sleep(1)
        description = await llm.complete_vision(
            prompt=VISION_PROMPT_MEDICAL,
            image_bytes=resized,
            media_type=media_type,
        )

    if any(p in description.lower() for p in _REFUSAL_PHRASES) or len(description.strip()) < 50:
        raise ValueError(
            f"Vision LLM refused or returned insufficient description for '{filename}' "
            f"({len(description.strip())} chars) — manual review needed."
        )

    effective_model = VISION_MODEL or PRIMARY_MODEL
    image_meta: dict = {
        "chunk_type": "image_description",
        "source_image_key": storage_key,
        "media_type": media_type,
        "original_filename": filename,
        "vision_model": effective_model,
        "description_length": len(description.strip()),
    }

    logger.info(
        "[EXTRACTOR] image described: %s → %d chars via %s",
        filename, image_meta["description_length"], effective_model,
    )
    return description, ChunkStrategy.IMAGE, image_meta


def extract_text(file_bytes: bytes, filename: str) -> tuple[str, ChunkStrategy]:
    """
    Extract plain text from *file_bytes*.

    Returns (text, strategy).
    Raises ValueError for unsupported extensions.
    """
    ext = Path(filename).suffix.lower()

    if ext in (".txt", ".md"):
        return _extract_plain(file_bytes), ChunkStrategy.SECTION

    if ext == ".pdf":
        return _extract_pdf(file_bytes), ChunkStrategy.SECTION

    if ext == ".docx":
        return _extract_docx(file_bytes), ChunkStrategy.SECTION

    if ext == ".csv":
        return _extract_csv(file_bytes), ChunkStrategy.ROW

    if ext == ".json":
        return _extract_json(file_bytes), ChunkStrategy.JSON_RECORD

    raise ValueError(f"Unsupported file type for RAG extraction: {ext!r}")


# ── Per-type helpers ──────────────────────────────────────────────────────────

def _extract_plain(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace")


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        import pypdf
    except ImportError:
        raise ImportError(
            "pypdf is not installed — PDF cannot be extracted. Run: pip install pypdf"
        )
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
        result = "\n\n".join(pages)
        logger.info("PDF extraction: %d pages, %d chars", len(reader.pages), len(result))
        if not result.strip():
            raise ValueError(
                f"PDF has {len(reader.pages)} page(s) but contains no extractable text — "
                "it may be a scanned or image-based PDF."
            )
        return result
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f"PDF extraction error: {exc}") from exc


def _extract_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "python-docx is not installed — DOCX cannot be extracted. Run: pip install python-docx"
        )
    try:
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        result = "\n\n".join(paragraphs)
        logger.info("DOCX extraction: %d paragraphs, %d chars", len(paragraphs), len(result))
        return result
    except Exception as exc:
        raise RuntimeError(f"DOCX extraction error: {exc}") from exc


def _extract_csv(file_bytes: bytes) -> str:
    """
    Serialize each CSV row as 'field: value, field: value, ...' on its own line.
    Each line will become one RAG chunk (ROW strategy).
    """
    import csv
    raw = _extract_plain(file_bytes)
    reader = csv.DictReader(io.StringIO(raw))
    rows = []
    for row in reader:
        row_text = ", ".join(f"{k}: {v}" for k, v in row.items() if v is not None and str(v).strip())
        if row_text:
            rows.append(row_text)
    if rows:
        logger.info("CSV extraction: %d rows", len(rows))
        return "\n".join(rows)
    # Fall back to raw text if CSV parsing yields nothing
    return raw


def _extract_json(file_bytes: bytes) -> str:
    """
    Serialize each top-level item as a 'key: value, key: value' string on its own line.
    Each line will become one RAG chunk (JSON_RECORD strategy).
    Mirrors the CSV serialization format so field values are co-located as natural text,
    not split across lines by JSON indentation, and free of JSON syntax noise.
    """
    raw = _extract_plain(file_bytes)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            lines = [_dict_to_kv(item) if isinstance(item, dict) else str(item) for item in data]
            logger.info("JSON extraction: %d records", len(lines))
            return "\n".join(lines)
        if isinstance(data, dict):
            return _dict_to_kv(data)
    except json.JSONDecodeError:
        pass
    return raw


def _dict_to_kv(record: dict) -> str:
    """Serialize a dict as 'key: value, key: value' — natural language, no JSON syntax."""
    pairs = []
    for k, v in record.items():
        if isinstance(v, (dict, list)):
            pairs.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            pairs.append(f"{k}: {v}")
    return ", ".join(pairs)
