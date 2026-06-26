"""
Documents router — file uploads, listing, deletion, and RAG index status.

Upload flow (async indexing):
  1. Validate file type and content
  2. Save to storage backend (local disk or Supabase)
  3. Kick off RAG indexing in a FastAPI BackgroundTask — returns immediately
  4. Client polls GET /api/documents/index-status to track progress

The background task handles: extract → chunk → embed → store in rag_chunks.
Index status is tracked in the rag_documents MongoDB collection.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from auth.dependencies import get_admin_user, get_current_user
from database.mongodb import get_db
from services.storage_service import get_storage_service

router = APIRouter()
logger = logging.getLogger("voxa.router.documents")

ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".csv", ".json",
    ".doc", ".docx", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
}

# Extensions the RAG indexer knows how to extract text from.
# Others are stored but not indexed (no error — just no chunks).
_RAG_SUPPORTED = {
    ".txt", ".md", ".pdf", ".docx", ".csv", ".json",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
}


async def _run_indexing(user_id: str, filename: str, file_bytes: bytes) -> None:
    """Background task: run the full RAG indexing pipeline for one uploaded file."""
    db = get_db()
    if db is None:
        logger.warning("[DOCUMENTS] background indexing skipped — DB unavailable: %s", filename)
        return
    try:
        from config.settings import RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP
        from rag.indexer import index_document
        result = await index_document(
            db, user_id, filename, file_bytes,
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
        )
        logger.info(
            "[DOCUMENTS] indexing complete: %s status=%s chunks=%d skipped=%s",
            filename, result["index_status"], result["chunk_count"], result["skipped"],
        )
    except Exception as exc:
        logger.error("[DOCUMENTS] background indexing failed for %s: %s", filename, exc, exc_info=True)


@router.get("/")
async def list_documents(current_user: dict = Depends(get_current_user)):
    """
    List all documents for the current user, joined with RAG index status.
    Returns three-state records: indexed, pending (upload/crash window), or missing (orphan).
    """
    storage = get_storage_service()
    user_id = str(current_user["id"])
    prefix = f"documents/{user_id}/"
    stored = storage.list_prefix(prefix=prefix)

    storage_filenames = [Path(d.key).name for d in stored]
    storage_map = {Path(d.key).name: d for d in stored}

    db = get_db()
    if db is None:
        # Fallback: return storage-only records with no index status
        return {
            "documents": [
                {
                    "filename": Path(d.key).name,
                    "path": d.key,
                    "url": d.url,
                    "size": d.size,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                    "index_status": "unknown",
                    "chunk_count": None,
                }
                for d in stored
            ]
        }

    from rag.document_store import list_user_documents
    rag_records = await list_user_documents(db, user_id, storage_filenames)

    docs = []
    for record in rag_records:
        filename = record["filename"]
        storage_obj = storage_map.get(filename)
        docs.append({
            "filename": filename,
            "path": storage_obj.key if storage_obj else None,
            "url": storage_obj.url if storage_obj else None,
            "size": storage_obj.size if storage_obj else None,
            "updated_at": storage_obj.updated_at.isoformat() if storage_obj and storage_obj.updated_at else None,
            "index_status": record.get("index_status"),
            "chunk_count": record.get("chunk_count"),
            "indexed_at": record.get("indexed_at").isoformat() if record.get("indexed_at") else None,
            "chunk_strategy": record.get("chunk_strategy"),
            "error_message": record.get("error_message"),
        })

    return {"documents": docs}


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a document. Saves to storage synchronously, then indexes in background.
    Returns immediately with status='processing'; poll /index-status for completion.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    user_id = str(current_user["id"])
    filename = Path(file.filename).name
    key = f"documents/{user_id}/{filename}"

    stored = get_storage_service().save_bytes(key, content, file.content_type)

    # Kick off RAG indexing in the background — returns immediately to the client
    if ext in _RAG_SUPPORTED:
        background_tasks.add_task(_run_indexing, user_id, filename, content)
        rag_status = "processing"
    else:
        rag_status = "not_supported"
        logger.info("[DOCUMENTS] %s not RAG-indexed (extension %s not supported)", filename, ext)

    return {
        "status": "ok",
        "rag_status": rag_status,
        "document": {
            "filename": filename,
            "path": stored.key,
            "url": stored.url,
            "size": stored.size,
            "updated_at": stored.updated_at.isoformat() if stored.updated_at else None,
        },
    }


@router.delete("/{filename}")
async def delete_document(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a document from storage and remove all its RAG chunks and metadata.
    Idempotent — safe to call even if the document was never indexed.
    """
    user_id = str(current_user["id"])
    key = f"documents/{user_id}/{filename}"

    # Remove from storage
    storage = get_storage_service()
    try:
        storage.delete(key)
    except Exception as exc:
        logger.warning("[DOCUMENTS] storage delete failed for %s: %s", filename, exc)

    # Remove RAG chunks and metadata record
    db = get_db()
    chunks_deleted = 0
    if db is not None:
        try:
            from rag.indexer import delete_document as rag_delete
            chunks_deleted = await rag_delete(db, user_id, filename)
        except Exception as exc:
            logger.warning("[DOCUMENTS] RAG delete failed for %s: %s", filename, exc)

    return {
        "status": "ok",
        "filename": filename,
        "chunks_deleted": chunks_deleted,
    }


@router.get("/index-status")
async def get_index_status(current_user: dict = Depends(get_current_user)):
    """
    Return RAG index health for the current user.
    Counts documents by status: pending, indexed, failed, missing, stale.
    Stale = indexed under a different EMBEDDING_MODEL than currently configured.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    from rag.document_store import get_index_health
    health = await get_index_health(db, str(current_user["id"]))
    return {"index_health": health}


# @router.get("/debug")
# async def debug_rag(
#     query: str = "",
#     current_user: dict = Depends(get_current_user),
# ):
#     """
#     Debug endpoint — inspect what is stored in rag_chunks for this user and
#     optionally run a test retrieval.
#
#     GET /api/documents/debug                  → show stored chunks summary
#     GET /api/documents/debug?query=CareConnect → also run live retrieval
#     """
#     db = get_db()
#     if db is None:
#         raise HTTPException(status_code=503, detail="Database unavailable")
#
#     user_id = str(current_user["id"])
#     from rag.document_store import RAG_CHUNKS_COLLECTION, RAG_DOCUMENTS_COLLECTION
#
#     # Count and sample chunks
#     total_chunks = await db[RAG_CHUNKS_COLLECTION].count_documents({"user_id": user_id})
#     sample_cursor = db[RAG_CHUNKS_COLLECTION].find(
#         {"user_id": user_id},
#         {"_id": 0, "filename": 1, "chunk_index": 1, "text": 1, "embedding": 1},
#     ).limit(3)
#     sample_chunks = await sample_cursor.to_list(length=3)
#
#     # Summarize each chunk (don't return full embeddings)
#     chunk_preview = []
#     for c in sample_chunks:
#         has_embedding = c.get("embedding") is not None and len(c.get("embedding", [])) > 0
#         chunk_preview.append({
#             "filename": c.get("filename"),
#             "chunk_index": c.get("chunk_index"),
#             "text_preview": (c.get("text") or "")[:200],
#             "text_length": len(c.get("text") or ""),
#             "has_embedding": has_embedding,
#             "embedding_dims": len(c.get("embedding") or []),
#         })
#
#     # Document records
#     doc_cursor = db[RAG_DOCUMENTS_COLLECTION].find(
#         {"user_id": user_id},
#         {"_id": 0, "filename": 1, "index_status": 1, "chunk_count": 1,
#          "embedding_model": 1, "error_message": 1},
#     )
#     doc_records = await doc_cursor.to_list(length=20)
#
#     result = {
#         "user_id_prefix": user_id[:8] + "...",
#         "total_chunks_in_db": total_chunks,
#         "documents": doc_records,
#         "chunk_sample": chunk_preview,
#     }
#
#     # Optional: live retrieval test
#     if query:
#         from orchestrator.semantic_expander import get_query_embedding
#         from rag.retriever import retrieve_chunks
#         import os
#         query_vector = await get_query_embedding(query) if os.getenv("EMBEDDING_MODEL") else None
#         chunks, filenames = await retrieve_chunks(db, query_vector, query, user_id, top_k=5)
#         result["test_query"] = query
#         result["test_retrieval"] = {
#             "chunks_found": len(chunks),
#             "filenames": filenames,
#             "top_chunk_text": chunks[0]["text"][:300] if chunks else None,
#             "top_chunk_score": chunks[0].get("score") if chunks else None,
#         }
#
#     return result


# ── Org-level (shared) document endpoints ─────────────────────────────────────
# All endpoints below require is_admin=True and org_id set on the caller's JWT.

async def _run_org_indexing(
    org_id: str, user_id: str, filename: str, file_bytes: bytes
) -> None:
    """Background task: index an admin-uploaded org document."""
    db = get_db()
    if db is None:
        logger.warning("[DOCUMENTS] org indexing skipped — DB unavailable: %s", filename)
        return
    try:
        from config.settings import RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP
        from rag.indexer import index_document
        result = await index_document(
            db, user_id, filename, file_bytes,
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
            scope="org",
            org_id=org_id,
        )
        logger.info(
            "[DOCUMENTS] org indexing complete: %s status=%s chunks=%d",
            filename, result["index_status"], result["chunk_count"],
        )
    except Exception as exc:
        logger.error("[DOCUMENTS] org indexing failed for %s: %s", filename, exc, exc_info=True)


@router.get("/org")
async def list_org_documents(admin_user: dict = Depends(get_admin_user)):
    """
    List all org-level shared documents, joined with RAG index status.
    Admin-only.
    """
    org_id = str(admin_user["org_id"])
    storage = get_storage_service()
    prefix = f"org/{org_id}/"
    stored = storage.list_prefix(prefix=prefix)

    storage_filenames = [Path(d.key).name for d in stored]
    storage_map = {Path(d.key).name: d for d in stored}

    db = get_db()
    if db is None:
        return {
            "documents": [
                {
                    "filename": Path(d.key).name,
                    "path": d.key,
                    "url": d.url,
                    "size": d.size,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                    "index_status": "unknown",
                    "chunk_count": None,
                    "scope": "org",
                }
                for d in stored
            ]
        }

    from rag.document_store import list_org_documents as _list_org
    rag_records = await _list_org(db, org_id, storage_filenames)

    docs = []
    for record in rag_records:
        filename = record["filename"]
        storage_obj = storage_map.get(filename)
        docs.append({
            "filename": filename,
            "path": storage_obj.key if storage_obj else None,
            "url": storage_obj.url if storage_obj else None,
            "size": storage_obj.size if storage_obj else None,
            "updated_at": storage_obj.updated_at.isoformat() if storage_obj and storage_obj.updated_at else None,
            "index_status": record.get("index_status"),
            "chunk_count": record.get("chunk_count"),
            "indexed_at": record.get("indexed_at").isoformat() if record.get("indexed_at") else None,
            "chunk_strategy": record.get("chunk_strategy"),
            "error_message": record.get("error_message"),
            "scope": "org",
        })

    return {"documents": docs}


@router.post("/org/upload")
async def upload_org_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    admin_user: dict = Depends(get_admin_user),
):
    """
    Upload a shared org-level reference document.
    Stored under org/<org_id>/<filename> and indexed with scope="org".
    Admin-only — regular users cannot call this endpoint.
    Returns immediately; poll /org/index-status for completion.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    org_id  = str(admin_user["org_id"])
    user_id = str(admin_user["id"])
    filename = Path(file.filename).name
    key = f"org/{org_id}/{filename}"

    stored = get_storage_service().save_bytes(key, content, file.content_type)

    if ext in _RAG_SUPPORTED:
        background_tasks.add_task(_run_org_indexing, org_id, user_id, filename, content)
        rag_status = "processing"
    else:
        rag_status = "not_supported"

    return {
        "status": "ok",
        "rag_status": rag_status,
        "scope": "org",
        "document": {
            "filename": filename,
            "path": stored.key,
            "url": stored.url,
            "size": stored.size,
            "updated_at": stored.updated_at.isoformat() if stored.updated_at else None,
        },
    }


@router.delete("/org/{filename}")
async def delete_org_document(
    filename: str,
    admin_user: dict = Depends(get_admin_user),
):
    """
    Delete a shared org document from storage and remove all its RAG chunks.
    Admin-only. Idempotent.
    """
    org_id  = str(admin_user["org_id"])
    user_id = str(admin_user["id"])
    key = f"org/{org_id}/{filename}"

    storage = get_storage_service()
    try:
        storage.delete(key)
    except Exception as exc:
        logger.warning("[DOCUMENTS] org storage delete failed for %s: %s", filename, exc)

    db = get_db()
    chunks_deleted = 0
    if db is not None:
        try:
            from rag.indexer import delete_document as rag_delete
            chunks_deleted = await rag_delete(db, user_id, filename, scope="org", org_id=org_id)
        except Exception as exc:
            logger.warning("[DOCUMENTS] org RAG delete failed for %s: %s", filename, exc)

    return {
        "status": "ok",
        "filename": filename,
        "scope": "org",
        "chunks_deleted": chunks_deleted,
    }


@router.get("/org/index-status")
async def get_org_index_status(admin_user: dict = Depends(get_admin_user)):
    """Return RAG index health for the org's shared documents. Admin-only."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    from rag.document_store import get_org_index_health
    health = await get_org_index_health(db, str(admin_user["org_id"]))
    return {"index_health": health, "scope": "org"}
