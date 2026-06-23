"""
Text chunker — splits extracted text into chunks using a ChunkStrategy.

Strategies:
  SLIDING_WINDOW  word-boundary sliding window with configurable size and overlap
  SECTION         paragraph-aware: split on double-newlines first, sub-chunk if too long
  ROW             one line = one chunk (CSV rows, already serialised by extractor)
  JSON_RECORD     one line = one chunk (JSON records, already serialised by extractor)
"""

import logging

from rag.extractor import ChunkStrategy

logger = logging.getLogger("voxa.rag.chunker")


def chunk_text(
    text: str,
    strategy: ChunkStrategy,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """
    Split *text* into chunks using *strategy*.
    Returns an empty list when *text* has no content.
    """
    if not text or not text.strip():
        return []

    if strategy == ChunkStrategy.ROW:
        return _chunk_by_line(text)

    if strategy == ChunkStrategy.JSON_RECORD:
        return _chunk_by_line(text)

    if strategy == ChunkStrategy.SECTION:
        return _chunk_by_section(text, chunk_size, overlap)

    if strategy == ChunkStrategy.IMAGE:
        return _chunk_image_description(text, chunk_size, overlap)

    return _chunk_sliding_window(text, chunk_size, overlap)


# ── Strategy implementations ──────────────────────────────────────────────────

def _chunk_sliding_window(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Word-boundary sliding window.
    Advances by (chunk_size - overlap) words per step so adjacent chunks share
    *overlap* words — prevents cutting a sentence mid-thought at a boundary.
    """
    words = text.split()
    if not words:
        return []

    step = max(1, chunk_size - overlap)
    chunks: list[str] = []
    start = 0

    while start < len(words):
        chunk = " ".join(words[start: start + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
        start += step

    logger.debug("sliding_window: %d words → %d chunks", len(words), len(chunks))
    return chunks


def _chunk_by_section(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Paragraph-aware chunker for DOCX / structured text.

    Splits on double-newlines (paragraph / heading breaks) first.
    Sections that fit within chunk_size are kept as-is.
    Sections that exceed chunk_size are further split with the sliding window.
    """
    sections = [s.strip() for s in text.split("\n\n") if s.strip()]
    chunks: list[str] = []

    for section in sections:
        words = section.split()
        if len(words) <= chunk_size:
            chunks.append(section)
        else:
            sub = _chunk_sliding_window(section, chunk_size, overlap)
            chunks.extend(sub)

    logger.debug("section: %d sections → %d chunks", len(sections), len(chunks))
    return chunks


def _chunk_image_description(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Image descriptions are typically 200–500 words — return as a single chunk.
    Only splits when the description is unusually long (> chunk_size × 3 words),
    in which case section-based splitting preserves semantic coherence.
    """
    words = text.split()
    if len(words) <= chunk_size * 3:
        return [text]
    logger.debug("image_description: long description (%d words) — splitting by section", len(words))
    return _chunk_by_section(text, chunk_size, overlap)


def _chunk_by_line(text: str) -> list[str]:
    """
    One non-empty line = one chunk.
    Used for CSV rows and JSON records — the extractor already serialised each
    record as a single line, so no further splitting is needed.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    logger.debug("line: %d chunks", len(lines))
    return lines
