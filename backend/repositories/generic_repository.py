"""
Generic async MongoDB repository.

Works with any collection by name — no hardcoded schema assumptions.
Used by the orchestrator to fetch data dynamically from whatever
collections are discovered in the database.
"""

import logging
import re
import time
from typing import Any, Optional

import motor.motor_asyncio

from config.settings import MONGO_CHATS_COLLECTION, MONGO_USERS_COLLECTION, SESSIONS_COLLECTION
from utils.helpers import sanitize_doc

logger = logging.getLogger("voxa.repository")

# Cached collection metadata: collection_name → {fields, sample_doc, last_seen}
_metadata_cache: dict[str, dict] = {}
_CACHE_TTL_SECONDS = 300  # refresh every 5 minutes
_INTERNAL_COLLECTIONS = {
    MONGO_USERS_COLLECTION,
    MONGO_CHATS_COLLECTION,
    SESSIONS_COLLECTION,
    "system.indexes",
    # RAG collections — managed by rag/document_store.py, not user-queryable
    "rag_documents",
    "rag_chunks",
}


def _flatten_doc(doc: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested MongoDB documents into dot-path keys for search metadata."""
    if isinstance(doc, dict):
        flattened: dict[str, Any] = {}
        for key, value in doc.items():
            if key == "_id":
                continue
            path = f"{prefix}.{key}" if prefix else key
            flattened.update(_flatten_doc(value, path))
        return flattened
    if isinstance(doc, list):
        flattened = {}
        for idx, item in enumerate(doc[:3]):
            path = f"{prefix}.{idx}" if prefix else str(idx)
            flattened.update(_flatten_doc(item, path))
        return flattened
    return {prefix: doc} if prefix else {}


def _clean_array_path(path: str) -> str:
    """Convert 'field.0.subfield.2.name' → 'field.subfield.name'.

    MongoDB queries on 'field.subfield' automatically traverse arrays, whereas
    'field.0.subfield' only matches the first array element. Removing numeric
    segments makes the regex search scan all array elements.
    """
    return re.sub(r"\.\d+", "", path)


def _text_preview(doc: dict[str, Any], max_chars: int = 1200) -> str:
    values: list[str] = []
    for value in _flatten_doc(doc).values():
        if isinstance(value, (str, int, float, bool)):
            values.append(str(value))
    return " ".join(values)[:max_chars]


class GenericRepository:
    """
    Provides async CRUD operations and schema introspection for any
    MongoDB collection, identified by name at runtime.
    """

    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorDatabase) -> None:
        self._db = db

    # ── Collection discovery ──────────────────────────────────────────────────

    async def list_collections(self) -> list[str]:
        """Return the names of all collections in the database."""
        names = await self._db.list_collection_names()
        visible = [
            name for name in names
            if name not in _INTERNAL_COLLECTIONS
            and "." not in name  # skip "main.patients" style Compass-export artefacts
        ]
        logger.info("Mongo collections discovered: all=%s dataset=%s", names, visible)
        return visible

    async def get_collection_metadata(
        self, force_refresh: bool = False
    ) -> dict[str, dict]:
        """
        Return a dict mapping collection_name → {fields, doc_count}.
        Results are cached for CACHE_TTL_SECONDS to avoid repeated round-trips.
        """
        now = time.time()
        # Use cached result if fresh
        if not force_refresh and _metadata_cache.get("_ts", 0) + _CACHE_TTL_SECONDS > now:
            meta = {k: v for k, v in _metadata_cache.items() if k != "_ts"}
            if meta:
                return meta

        collection_names = await self.list_collections()
        fresh: dict[str, dict] = {}

        for name in collection_names:
            try:
                coll = self._db[name]
                count = await coll.count_documents({})
                samples = await coll.find({}).limit(5).to_list(length=5)
                field_names: list[str] = []
                searchable_fields: list[str] = []
                sample_text_parts: list[str] = []

                for sample in samples:
                    flattened = _flatten_doc(sample)
                    sample_text_parts.append(_text_preview(sample))
                    for field, value in flattened.items():
                        clean = _clean_array_path(field)
                        if clean not in field_names:
                            field_names.append(clean)
                        if isinstance(value, str) and clean not in searchable_fields:
                            searchable_fields.append(clean)

                fresh[name] = {
                    "fields": field_names[:40],
                    "searchable_fields": searchable_fields[:30],
                    "sample_text": " ".join(sample_text_parts)[:2400],
                    "doc_count": count,
                }
                logger.info(
                    "Collection metadata: name=%s docs=%s fields=%s searchable_fields=%s",
                    name,
                    count,
                    len(field_names),
                    len(searchable_fields),
                )
            except Exception as exc:
                logger.debug(f"Metadata failed for '{name}': {exc}")
                fresh[name] = {"fields": [], "doc_count": 0}

        _metadata_cache.clear()
        _metadata_cache.update(fresh)
        _metadata_cache["_ts"] = now

        logger.info(f"Collection metadata refreshed: {len(fresh)} collections")
        return fresh

    # ── Data fetching ─────────────────────────────────────────────────────────

    async def find(
        self,
        collection_name: str,
        query: Optional[dict] = None,
        limit: Optional[int] = None,
        skip: int = 0,
        sort: Optional[list[tuple]] = None,
        projection: Optional[dict] = None,
    ) -> list[dict]:
        """
        Fetch documents from *collection_name* matching *query*.
        limit=0 (default) returns all matching documents.
        limit=None fetches every matching document (no cap).
        Returns sanitized (JSON-serializable) dicts.
        """
        coll = self._db[collection_name]
        cursor = coll.find(query or {}, projection or {})
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        docs = await cursor.to_list(length=limit)
        return [sanitize_doc(d) for d in docs]

    async def find_paginated(
        self,
        collection_name: str,
        query: Optional[dict] = None,
        page: int = 1,
        page_size: int = 50,
        sort: Optional[list[tuple]] = None,
    ) -> tuple[list[dict], int]:
        """
        Fetch one page of documents and the total matching count.
        Returns (docs_for_page, total_matching_count).
        """
        total = await self.count(collection_name, query)
        skip = (page - 1) * page_size
        coll = self._db[collection_name]
        cursor = coll.find(query or {})
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return [sanitize_doc(d) for d in docs], total

    async def keyword_search_paginated(
        self,
        collection_name: str,
        keywords: list[str],
        fields: Optional[list[str]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """
        Paginated keyword search.
        Returns (docs_for_page, total_matching_count).
        """
        if not keywords:
            return await self.find_paginated(collection_name, page=page, page_size=page_size)

        if fields is None:
            sample = await self.find_one(collection_name, {})
            fields = (
                [k for k, v in sample.items() if isinstance(v, str)]
                if sample
                else ["name"]
            )

        or_clauses: list[dict] = []
        for kw in keywords[:5]:
            escaped = re.escape(kw)
            for field in fields[:10]:
                or_clauses.append({field: {"$regex": escaped, "$options": "i"}})

        if not or_clauses:
            return await self.find_paginated(collection_name, page=page, page_size=page_size)

        mongo_filter = {"$or": or_clauses}
        docs, total = await self.find_paginated(
            collection_name, mongo_filter, page=page, page_size=page_size
        )
        logger.info(
            "Keyword search paginated: collection=%s keywords=%s page=%d total=%d returned=%d",
            collection_name, keywords[:5], page, total, len(docs),
        )
        return docs, total

    async def count(self, collection_name: str, query: Optional[dict] = None) -> int:
        """Count documents matching *query* in *collection_name*."""
        return await self._db[collection_name].count_documents(query or {})

    async def aggregate(
        self, collection_name: str, pipeline: list[dict]
    ) -> list[dict]:
        """Run an aggregation pipeline and return sanitized results."""
        cursor = self._db[collection_name].aggregate(pipeline)
        docs = await cursor.to_list(length=None)
        return [sanitize_doc(d) for d in docs]

    async def find_one(
        self,
        collection_name: str,
        query: dict,
        projection: Optional[dict] = None,
    ) -> Optional[dict]:
        doc = await self._db[collection_name].find_one(query, projection or {})
        return sanitize_doc(doc) if doc else None

    async def insert_one(self, collection_name: str, document: dict) -> str:
        result = await self._db[collection_name].insert_one(document)
        return str(result.inserted_id)

    async def insert_many(
        self, collection_name: str, documents: list[dict]
    ) -> list[str]:
        result = await self._db[collection_name].insert_many(documents)
        return [str(oid) for oid in result.inserted_ids]

    async def update_one(
        self,
        collection_name: str,
        query: dict,
        update: dict,
        upsert: bool = False,
    ) -> int:
        result = await self._db[collection_name].update_one(
            query, update, upsert=upsert
        )
        return result.modified_count

    async def delete_one(self, collection_name: str, query: dict) -> int:
        result = await self._db[collection_name].delete_one(query)
        return result.deleted_count

    # ── Keyword search ────────────────────────────────────────────────────────

    async def vector_search(
        self,
        collection_name: str,
        query_vector: list[float],
        vector_field: str = "embedding",
        index_name: str = "vector_index",
        limit: int = 15,
    ) -> list[dict]:
        """
        Run MongoDB Atlas $vectorSearch on *collection_name*.

        Requires:
          - MongoDB Atlas cluster (not local mongod)
          - A vector search index named *index_name* on *vector_field*
          - Documents pre-indexed with their embedding vectors

        Returns [] silently when the index is absent or the call fails,
        so the caller can fall back to keyword search transparently.
        """
        pipeline = [
            {
                "$vectorSearch": {
                    "index": index_name,
                    "path": vector_field,
                    "queryVector": query_vector,
                    "numCandidates": limit * 5,
                    "limit": limit,
                }
            },
            {
                "$addFields": {"_search_score": {"$meta": "vectorSearchScore"}}
            },
        ]
        try:
            results = await self.aggregate(collection_name, pipeline)
            logger.info(
                "Vector search: collection=%s index=%s returned=%s",
                collection_name,
                index_name,
                len(results),
            )
            return results
        except Exception as exc:
            logger.debug(
                "Vector search unavailable for '%s' (index missing?): %s",
                collection_name,
                exc,
            )
            return []

    async def keyword_search(
        self,
        collection_name: str,
        keywords: list[str],
        fields: Optional[list[str]] = None,
        extra_filter: Optional[dict] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """
        Search *collection_name* for documents where any of *fields* match
        any of *keywords* (case-insensitive regex).

        extra_filter is ANDed with the keyword $or so callers can narrow
        results using structured conditions (e.g. from QueryMeta.filters).
        limit=0 (default) returns all matching documents.
        limit=None returns all matching documents.
        Falls back to a full-collection fetch if no matches found.
        """
        if not keywords:
            base = extra_filter or {}
            return await self.find(collection_name, base, limit=limit)

        if fields is None:
            # Infer searchable string fields from a sample document
            sample = await self.find_one(collection_name, {})
            fields = (
                [k for k, v in sample.items() if isinstance(v, str)]
                if sample
                else ["name"]
            )

        # Build $or across all (field, keyword) combinations
        or_clauses: list[dict] = []
        for kw in keywords[:8]:                  # limit to top-8 keywords
            escaped = re.escape(kw)
            for field in fields[:15]:            # limit to top-15 fields
                or_clauses.append(
                    {field: {"$regex": escaped, "$options": "i"}}
                )

        if not or_clauses:
            base = extra_filter or {}
            return await self.find(collection_name, base, limit=limit)

        # Combine keyword OR with any structured filter via AND
        if extra_filter:
            query: dict = {"$and": [{"$or": or_clauses}, extra_filter]}
        else:
            query = {"$or": or_clauses}

        results = await self.find(collection_name, query, limit=limit)
        logger.info(
            "Keyword search: collection=%s keywords=%s fields=%s extra_filter=%s returned=%s",
            collection_name,
            keywords[:5],
            fields[:10],
            bool(extra_filter),
            len(results),
        )
        return results
