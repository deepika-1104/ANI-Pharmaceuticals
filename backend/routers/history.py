"""
History router — conversation history sync between client and server.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from models.requests import HistorySyncRequest
from services import chat_service

router = APIRouter()
logger = logging.getLogger("voxa.router.history")


@router.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    """Return all stored conversations for the current user."""
    try:
        conversations = await chat_service.get_user_chats(current_user["id"])
        return {"conversations": conversations}
    except Exception as exc:
        logger.error(f"get_history error: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve history")


@router.post("/sync")
async def sync_history(
    body: HistorySyncRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Upsert the full conversation map from the frontend.
    Use an empty dict to clear all history.
    """
    try:
        await chat_service.sync_user_chats(current_user["id"], body.conversations)
        return {"status": "ok", "synced_count": len(body.conversations)}
    except Exception as exc:
        logger.error(f"sync_history error: {exc}")
        raise HTTPException(status_code=500, detail="Failed to sync history")
