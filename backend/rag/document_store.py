"""
Document store — manages rag_documents (metadata) and rag_chunks (content).

rag_documents : one record per uploaded file — tracks indexing status, hash, strategy.
rag_chunks    : many records per file — the actual text chunks and embedding vectors.

Separation keeps index health queries cheap (no chunk scanning) and lets the
retriever filter by user_id without touching the metadata collection.

Scopes
------
Every document and chunk carries a `scope` field:
  "user"  — personal upload, visible only to the uploading user (user_id match)
  "org"   — shared upload by an admin, visible to all users in the same org (org_id match)

Retrieval queries union both scopes so a user automatically sees org-level reference
documents alongside their own uploads.
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import motor.motor_asyncio

logger = logging.getLogger("voxa.rag.document_store")

RAG_DOCUMENTS_COLLECTION = "rag_documents"
RAG_CHUNKS_COLLECTION = "rag_chunks"


async def init_rag_indexes(db: motor.motor_asyncio.AsyncIOMotorDatabase) -> None:
    """
    Create mandatory indexes on rag_chunks at startup.
    These are regular MongoDB indexes (not Atlas vector indexes) — no manual
    Atlas configuration required.

    Without {doc_id: 1}, every file deletion scans the full rag_chunks collection.
    Without {user_id: 1, doc_id: 1}, Atlas $vectorSearch filter has no supporting index.
    Without {org_id: 1, scope: 1}, org-scoped retrieval scans the full collection.

    # TODO: Add before production load:
    #   await db[RAG_DOCUMENTS_COLLECTION].create_index([("user_id", 1)])
    #   await db[RAG_DOCUMENTS_COLLECTION].create_index(
    #       [("user_id", 1), ("filename", 1)], unique=True
    #   )
    # The unique index also prevents duplicate rag_documents records on concurrent
    # uploads of the same file by the same user.
    """
    await db[RAG_CHUNKS_COLLECTION].create_index([("doc_id", 1)])
    await db[RAG_CHUNKS_COLLECTION].create_index([("user_id", 1), ("doc_id", 1)])
    await db[RAG_CHUNKS_COLLECTION].create_index([("org_id", 1), ("scope", 1)])
    logger.info("RAG collection indexes initialized")


# ── ID / hash helpers ─────────────────────────────────────────────────────────

def compute_file_hash(file_bytes: bytes) -> str:
    """SHA-256 hex digest of raw file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def make_doc_id(user_id: str, filename: str) -> str:
    """
    Stable identity-based ID: sha256(user_id:filename)[:16].
    Same user + same filename → same doc_id on every re-upload.
    Different users uploading the same filename → different doc_ids (user-scoped).
    """
    return hashlib.sha256(f"{user_id}:{filename}".encode()).hexdigest()[:16]


def make_org_doc_id(org_id: str, filename: str) -> str:
    """
    Stable org-scoped ID: sha256(org:org_id:filename)[:16].
    Same org + same filename → same doc_id regardless of which admin uploaded it.
    """
    return hashlib.sha256(f"org:{org_id}:{filename}".encode()).hexdigest()[:16]


# ── rag_documents CRUD ────────────────────────────────────────────────────────

async def get_document_record(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    doc_id: str,
) -> Optional[dict]:
    return await db[RAG_DOCUMENTS_COLLECTION].find_one({"doc_id": doc_id}, {"_id": 0})


async def upsert_document_record(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    *,
    doc_id: str,
    user_id: str,
    filename: str,
    file_hash: str,
    file_size_bytes: int,
    index_status: str = "pending",
    chunk_strategy: Optional[str] = None,
    embedding_model: Optional[str] = None,
    chunk_count: Optional[int] = None,
    error_message: Optional[str] = None,
    indexed_at: Optional[datetime] = None,
    partial_index: Optional[bool] = None,
    metadata: Optional[dict] = None,
    scope: str = "user",
    org_id: Optional[str] = None,
) -> None:
    """
    Full upsert — $set overwrites ALL mutable fields so no stale values survive
    a re-upload (e.g. old chunk_strategy, old embedding_model).
    created_at is $setOnInsert only so it is never overwritten.
    """
    now = datetime.now(timezone.utc)
    await db[RAG_DOCUMENTS_COLLECTION].update_one(
        {"doc_id": doc_id},
        {
            "$set": {
                "doc_id": doc_id,
                "user_id": user_id,
                "filename": filename,
                "file_hash": file_hash,
                "file_size_bytes": file_size_bytes,
                "index_status": index_status,
                "chunk_strategy": chunk_strategy,
                "embedding_model": embedding_model,
                "chunk_count": chunk_count,
                "error_message": error_message,
                "indexed_at": indexed_at,
                "partial_index": partial_index,
                "metadata": metadata or {},
                "scope": scope,
                "org_id": org_id,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


async def update_document_status(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    doc_id: str,
    status: str,
    chunk_count: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    """Lightweight status-only update — used during indexing transitions."""
    update: dict = {
        "index_status": status,
        "updated_at": datetime.now(timezone.utc),
    }
    if chunk_count is not None:
        update["chunk_count"] = chunk_count
        update["indexed_at"] = datetime.now(timezone.utc)
    if error_message is not None:
        update["error_message"] = error_message
    await db[RAG_DOCUMENTS_COLLECTION].update_one(
        {"doc_id": doc_id}, {"$set": update}
    )


async def delete_document_record(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    doc_id: str,
) -> None:
    await db[RAG_DOCUMENTS_COLLECTION].delete_one({"doc_id": doc_id})


# ── rag_chunks CRUD ───────────────────────────────────────────────────────────

async def insert_chunks(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    chunks: list[dict],
) -> int:
    if not chunks:
        return 0
    result = await db[RAG_CHUNKS_COLLECTION].insert_many(chunks)
    return len(result.inserted_ids)


async def delete_document_chunks(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    doc_id: str,
) -> int:
    """Remove all chunks for doc_id. Idempotent — deleting 0 docs is not an error."""
    result = await db[RAG_CHUNKS_COLLECTION].delete_many({"doc_id": doc_id})
    return result.deleted_count


# ── List / health ─────────────────────────────────────────────────────────────

async def list_user_documents(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    user_id: str,
    storage_filenames: list[str],
) -> list[dict]:
    """
    Merge storage listing with rag_documents records.

    Three states handled explicitly:
      1. File in storage + rag_documents record   → return joined record
      2. File in storage + no rag_documents record → synthetic "pending" record
         (covers the async-indexing window and crash-before-write scenarios)
      3. rag_documents record + file not in storage → index_status: "missing"
         (orphaned record after out-of-band storage deletion)
    """
    storage_set = set(storage_filenames)

    cursor = db[RAG_DOCUMENTS_COLLECTION].find(
        {"user_id": user_id, "scope": "user"},
        {"_id": 0, "embedding": 0},
    )
    db_records: dict[str, dict] = {}
    async for doc in cursor:
        db_records[doc["filename"]] = doc

    result: list[dict] = []

    for filename in storage_set:
        if filename in db_records:
            result.append(db_records[filename])         # State 1
        else:
            result.append({                              # State 2
                "filename": filename,
                "index_status": "pending",
                "chunk_count": None,
                "indexed_at": None,
            })

    for filename, record in db_records.items():
        if filename not in storage_set:
            result.append({**record, "index_status": "missing"})  # State 3

    return result


async def list_org_documents(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    org_id: str,
    storage_filenames: list[str],
) -> list[dict]:
    """
    Merge storage listing with org-scoped rag_documents records.
    Same three-state logic as list_user_documents but filtered by org_id + scope="org".
    """
    storage_set = set(storage_filenames)

    cursor = db[RAG_DOCUMENTS_COLLECTION].find(
        {"org_id": org_id, "scope": "org"},
        {"_id": 0, "embedding": 0},
    )
    db_records: dict[str, dict] = {}
    async for doc in cursor:
        db_records[doc["filename"]] = doc

    result: list[dict] = []

    for filename in storage_set:
        if filename in db_records:
            result.append(db_records[filename])
        else:
            result.append({
                "filename": filename,
                "index_status": "pending",
                "chunk_count": None,
                "indexed_at": None,
            })

    for filename, record in db_records.items():
        if filename not in storage_set:
            result.append({**record, "index_status": "missing"})

    return result


async def get_index_health(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    user_id: str,
) -> dict:
    """Return per-status document counts for this user. Includes stale detection."""
    pipeline = [
        {"$match": {"user_id": user_id, "scope": "user"}},
        {"$group": {"_id": "$index_status", "count": {"$sum": 1}}},
    ]
    cursor = db[RAG_DOCUMENTS_COLLECTION].aggregate(pipeline)
    counts: dict[str, int] = {}
    async for doc in cursor:
        counts[doc["_id"]] = doc["count"]

    current_model = os.getenv("EMBEDDING_MODEL", "")
    stale_count = 0
    if current_model:
        stale_count = await db[RAG_DOCUMENTS_COLLECTION].count_documents({
            "user_id": user_id,
            "scope": "user",
            "index_status": "indexed",
            "embedding_model": {"$ne": current_model},
        })

    return {
        "pending": counts.get("pending", 0),
        "indexed": counts.get("indexed", 0),
        "failed":  counts.get("failed", 0),
        "missing": counts.get("missing", 0),
        "stale":   stale_count,
        "total":   sum(counts.values()),
    }


async def get_org_index_health(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    org_id: str,
) -> dict:
    """Return per-status document counts for an org's shared documents."""
    pipeline = [
        {"$match": {"org_id": org_id, "scope": "org"}},
        {"$group": {"_id": "$index_status", "count": {"$sum": 1}}},
    ]
    cursor = db[RAG_DOCUMENTS_COLLECTION].aggregate(pipeline)
    counts: dict[str, int] = {}
    async for doc in cursor:
        counts[doc["_id"]] = doc["count"]

    current_model = os.getenv("EMBEDDING_MODEL", "")
    stale_count = 0
    if current_model:
        stale_count = await db[RAG_DOCUMENTS_COLLECTION].count_documents({
            "org_id": org_id,
            "scope": "org",
            "index_status": "indexed",
            "embedding_model": {"$ne": current_model},
        })

    return {
        "pending": counts.get("pending", 0),
        "indexed": counts.get("indexed", 0),
        "failed":  counts.get("failed", 0),
        "missing": counts.get("missing", 0),
        "stale":   stale_count,
        "total":   sum(counts.values()),
    }
