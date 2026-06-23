"""
Batch embedder — generates dense vectors for text chunks via the OpenAI embeddings API.

Reuses the same EMBEDDING_MODEL / EMBEDDING_API_KEY / EMBEDDING_BASE_URL env vars
already consumed by orchestrator/semantic_expander.py, so no new configuration is needed.

Behaviour when EMBEDDING_MODEL is not set:
  Returns [None, None, ...] — same length as input.
  The indexer stores None in the embedding field; the retriever falls back to
  keyword search at query time. The pipeline degrades gracefully throughout.

Partial batch failure:
  A timeout or API error on one batch leaves None in the affected positions.
  The indexer detects any None in the vector list and marks the document as
  'failed' so it can be retried — no silent partial index.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("voxa.rag.embedder")

_BATCH_SIZE = 96  # safe upper bound for long chunks; OpenAI allows up to 2048 inputs


def _get_embedding_client():
    model = os.getenv("EMBEDDING_MODEL", "")
    if not model:
        return None, None
    try:
        from openai import AsyncOpenAI
        api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY") or ""
        base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
        return AsyncOpenAI(api_key=api_key, base_url=base_url), model
    except ImportError:
        logger.warning("openai package not installed — embeddings disabled")
        return None, None


async def embed_texts(texts: list[str]) -> list[Optional[list[float]]]:
    """
    Generate embeddings for *texts* in batches.

    Returns a list of the same length as *texts*:
      - list[float]  when embedding succeeded
      - None         when EMBEDDING_MODEL is unset OR the batch call failed

    Never raises — failures are logged and represented as None entries.
    """
    if not texts:
        return []

    client, model = _get_embedding_client()
    if client is None:
        logger.debug("EMBEDDING_MODEL not set — skipping embeddings for %d texts", len(texts))
        return [None] * len(texts)

    results: list[Optional[list[float]]] = [None] * len(texts)

    for batch_start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[batch_start: batch_start + _BATCH_SIZE]
        try:
            response = await client.embeddings.create(model=model, input=batch)
            for i, item in enumerate(response.data):
                results[batch_start + i] = item.embedding
            logger.debug(
                "Embedded batch %d–%d (%d vectors)",
                batch_start, batch_start + len(batch), len(batch),
            )
        except Exception as exc:
            logger.warning(
                "Embedding batch %d–%d failed: %s — positions left as None",
                batch_start, batch_start + len(batch), exc,
            )

    embedded_count = sum(1 for v in results if v is not None)
    logger.info(
        "embed_texts: %d/%d succeeded (model=%s)",
        embedded_count, len(texts), model,
    )
    return results
