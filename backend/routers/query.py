"""
Query router — direct non-conversational queries against the database.
Delegates to the same orchestrator used by the chat router.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import get_current_user
from orchestrator.query_orchestrator import get_orchestrator

router = APIRouter()
logger = logging.getLogger("voxa.router.query")


class QueryRequest(BaseModel):
    query: str
    conversation_id: str = ""


@router.post("/query")
async def execute_query(
    body: QueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    One-shot data query. Returns a structured response with no streaming.
    Use /chat for multi-turn conversation with memory.
    """
    try:
        result = await get_orchestrator().process(
            query=body.query,
            session_id=body.conversation_id,
        )
        return result.to_dict()
    except Exception as exc:
        logger.error(f"Query error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Query processing failed")
