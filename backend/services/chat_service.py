"""
Chat / conversation history service.
Stores one document per user in the 'chats' MongoDB collection.
Each document maps conversation_id → list of messages.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from config.settings import MONGO_CHATS_COLLECTION
from database.mongodb import get_db

logger = logging.getLogger("voxa.chat_service")


def _chats_collection():
    db = get_db()
    if db is None:
        raise RuntimeError("MongoDB is not connected")
    return db[MONGO_CHATS_COLLECTION]


async def get_user_chats(user_id: str) -> dict[str, Any]:
    """Return all conversations for *user_id*."""
    try:
        col = _chats_collection()
        doc = await col.find_one({"user_id": str(user_id)}, {"_id": 0, "conversations": 1})
        if not doc:
            return {}
        conversations = doc.get("conversations", {})
        return conversations if isinstance(conversations, dict) else {}
    except Exception as exc:
        logger.error(f"get_user_chats failed: {exc}")
        return {}


async def sync_user_chats(user_id: str, conversations: dict[str, Any]) -> None:
    """
    Upsert the full conversation map for *user_id*.
    Pass an empty dict to clear all conversations.
    """
    try:
        col = _chats_collection()
        await col.update_one(
            {"user_id": str(user_id)},
            {
                "$set": {
                    "conversations": conversations or {},
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "user_id": str(user_id),
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
    except Exception as exc:
        logger.error(f"sync_user_chats failed: {exc}")
        raise
