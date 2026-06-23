"""
DB Result Cache — cross-user, persistent cache for MongoDB aggregation and
sample-fetch results.

Cache key is derived from the structural query identity
  (intent, collections, filters, metrics, grouping, aggregations, time_range)
rather than raw query text, so two different phrasings that produce the same
data retrieval intent share the same cache entry.

Only the DB layer results are cached.  LLM narration always runs fresh so
each user gets a naturally worded response, not a stored string.

RAG queries (user_id present) are never cached — each user's uploaded
documents are private.

The cache is backed by a pickle file so entries survive server restarts.
The in-memory dict is the hot path; the file is written on every set() so
state is always recoverable after a restart.

TTL is controlled by the RESPONSE_CACHE_TTL env var (default: 14400 s / 4 h).
Set to 0 to disable caching entirely.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("voxa.cache")


class DbResultCache:
    """
    Thread-safe persistent cache for MongoDB aggregation and fetch results.

    Hot path: in-memory dict (fast reads).
    Persistence: pickle file written on every set() so entries survive restarts.
    Key: SHA-256 hash of the structural query identity.
    """

    def __init__(self, ttl: int = 14400, cache_file: Optional[Path] = None) -> None:
        self._ttl = ttl
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._file = cache_file

        if self._ttl > 0 and self._file:
            self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load entries from disk into the in-memory store on startup."""
        if not self._file or not self._file.exists():
            return
        try:
            with open(self._file, "rb") as fh:
                data = pickle.load(fh)
            if isinstance(data, dict):
                # Drop already-expired entries while loading
                now = time.monotonic()
                valid = {
                    k: v for k, v in data.items()
                    if isinstance(v, dict) and now - v.get("ts", 0) <= self._ttl
                }
                with self._lock:
                    self._store = valid
                logger.info(
                    "[CACHE] loaded %d valid entries from %s", len(valid), self._file
                )
        except Exception as exc:
            logger.warning("[CACHE] could not load cache file (%s) — starting empty", exc)
            self._store = {}

    def _save(self) -> None:
        """Write the current in-memory store to disk (called under lock)."""
        if not self._file:
            return
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file, "wb") as fh:
                pickle.dump(self._store, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as exc:
            logger.warning("[CACHE] could not write cache file: %s", exc)

    # ── Key construction ──────────────────────────────────────────────────────

    @staticmethod
    def make_key(intent: str, collections: list[str], query_meta) -> str:
        """
        Build a deterministic cache key from the parts that determine what
        data will be retrieved — not from raw query text.

        Two queries with different phrasings but identical intent + filters +
        collections + metrics will produce the same key.
        """
        key_data = {
            "intent": intent,
            "collections": sorted(collections),
            "filters": dict(sorted((query_meta.filters or {}).items())),
            "metrics": sorted(query_meta.metrics or []),
            "grouping": query_meta.grouping,
            "aggregations": sorted(query_meta.aggregations or []),
            "time_range": query_meta.time_range,
        }
        raw = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[dict[str, Any]]:
        """Return cached DB results, or None if missing or expired."""
        if self._ttl == 0:
            return None
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() - entry["ts"] > self._ttl:
                del self._store[key]
                self._save()
                return None
            logger.debug("[CACHE] hit  key=%s age_s=%.0f", key, time.monotonic() - entry["ts"])
            return entry["data"]

    def set(self, key: str, data: dict[str, Any]) -> None:
        """Store DB results under key and persist to disk. No-op when TTL is 0."""
        if self._ttl == 0:
            return
        with self._lock:
            self._store[key] = {"data": data, "ts": time.monotonic()}
            self._save()
        logger.debug("[CACHE] stored key=%s entries=%d", key, len(self._store))

    def clear(self) -> None:
        """Flush all entries and remove the cache file."""
        with self._lock:
            self._store.clear()
            if self._file and self._file.exists():
                try:
                    self._file.unlink()
                except Exception as exc:
                    logger.warning("[CACHE] could not delete cache file: %s", exc)
        logger.info("[CACHE] cleared")

    def evict_expired(self) -> int:
        """Remove all expired entries. Returns count evicted."""
        if self._ttl == 0:
            return 0
        now = time.monotonic()
        with self._lock:
            expired = [k for k, v in self._store.items() if now - v["ts"] > self._ttl]
            for k in expired:
                del self._store[k]
            if expired:
                self._save()
        if expired:
            logger.debug("[CACHE] evicted %d expired entries", len(expired))
        return len(expired)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    @property
    def ttl(self) -> int:
        return self._ttl


# ── Singleton ─────────────────────────────────────────────────────────────────

_cache: Optional[DbResultCache] = None


def get_db_cache() -> DbResultCache:
    global _cache
    if _cache is None:
        from config.settings import RESPONSE_CACHE_TTL, BACKEND_DIR
        cache_file = BACKEND_DIR / ".voxa_cache.pkl"
        _cache = DbResultCache(ttl=RESPONSE_CACHE_TTL, cache_file=cache_file)
        logger.info(
            "[CACHE] initialised — ttl=%ds (%s) file=%s",
            RESPONSE_CACHE_TTL,
            "disabled" if RESPONSE_CACHE_TTL == 0 else f"{RESPONSE_CACHE_TTL // 3600}h{(RESPONSE_CACHE_TTL % 3600) // 60}m",
            cache_file,
        )
    return _cache
