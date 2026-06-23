"""
Session-scoped conversation memory.

Keeps a short rolling window of recent interactions per session so the LLM
has context for follow-up questions. Backed by Redis (when configured) or an
in-process dict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
import json
import logging

from config.settings import (
    MEMORY_BACKEND,
    MEMORY_CONTEXT_WINDOW,
    MEMORY_MAX_INTERACTIONS,
    REDIS_URL,
)

logger = logging.getLogger("voxa.memory")

MEMORY_COMPRESSION_THRESHOLD = max(MEMORY_CONTEXT_WINDOW + 1, MEMORY_MAX_INTERACTIONS // 2)


@dataclass
class MemoryEntry:
    query: str
    response: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SessionMemory:
    session_id: str
    entries: list[MemoryEntry] = field(default_factory=list)
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MemoryService:
    """
    Rolling conversation memory with optional Redis persistence.
    Thread-safe for concurrent requests.
    """

    def __init__(self) -> None:
        self.context_window = max(1, MEMORY_CONTEXT_WINDOW)
        self.max_interactions = max(self.context_window, MEMORY_MAX_INTERACTIONS)
        self._store: dict[str, SessionMemory] = {}
        self._lock = RLock()
        self._redis = self._init_redis()

    def _init_redis(self):
        if MEMORY_BACKEND != "redis" or not REDIS_URL:
            return None
        try:
            import redis
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            client.ping()
            logger.info("Conversation memory using Redis")
            return client
        except Exception as exc:
            logger.warning(f"Redis unavailable, using in-memory store: {exc}")
            return None

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """
        Return the conversation history as a list of {"role":…, "content":…} dicts
        ready to pass to the LLM.
        """
        memory = self._load(session_id)
        messages: list[dict[str, str]] = []
        for entry in memory.entries[-self.context_window:]:
            messages.append({"role": "user", "content": entry.query})
            messages.append({"role": "assistant", "content": entry.response})
        return messages

    def append(self, session_id: str, query: str, response: str) -> None:
        memory = self._load(session_id)
        memory.entries.append(MemoryEntry(query=query, response=response))
        # Keep only the most recent interactions
        if len(memory.entries) > self.max_interactions:
            memory.entries = memory.entries[-self.max_interactions:]
        memory.updated_at = datetime.now(timezone.utc).isoformat()
        self._save(memory)

    def clear(self, session_id: str) -> None:
        if self._redis:
            self._redis.delete(self._key(session_id))
            return
        with self._lock:
            self._store.pop(session_id, None)

    def _load(self, session_id: str) -> SessionMemory:
        if self._redis:
            raw = self._redis.get(self._key(session_id))
            if raw:
                try:
                    data = json.loads(raw)
                    return SessionMemory(
                        session_id=data["session_id"],
                        entries=[MemoryEntry(**e) for e in data.get("entries", [])],
                        updated_at=data.get("updated_at", ""),
                    )
                except Exception:
                    pass
            return SessionMemory(session_id=session_id)
        with self._lock:
            return self._store.get(session_id, SessionMemory(session_id=session_id))

    def _save(self, memory: SessionMemory) -> None:
        if self._redis:
            from dataclasses import asdict
            self._redis.set(self._key(memory.session_id), json.dumps(asdict(memory)))
            return
        with self._lock:
            self._store[memory.session_id] = memory

    @staticmethod
    def _key(session_id: str) -> str:
        return f"voxa:memory:{session_id}"


_memory_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
