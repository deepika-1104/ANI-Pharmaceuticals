"""
Health router — fast status check for load balancers and monitoring.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth.dependencies import get_current_user
from config.settings import LLM_PROVIDER, STT_AVAILABLE, LLM_API_KEY
from database.mongodb import is_connected
from services.llm_service import check_llm_health
from services.response_cache import get_db_cache

router = APIRouter()
logger = logging.getLogger("voxa.router.health")


async def _require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@router.get("/health")
async def health(request: Request):
    """Fast liveness probe — always responds, no heavy checks."""
    ready = getattr(request.app.state, "ready", False)
    return {
        "status": "ok",
        "ready": ready,
        "version": "2.0.0",
    }


# @router.post("/cache/clear")
# async def cache_clear(admin: dict = Depends(_require_admin)):
#     """Flush the DB result cache. Requires role: admin."""
#     cache = get_db_cache()
#     removed = cache.size
#     cache.clear()
#     logger.info("[CACHE] flushed by admin=%s — removed %d entries", admin.get("id"), removed)
#     return {"cleared": True, "entries_removed": removed}


# @router.get("/health/detailed")
# async def health_detailed():
#     """Full health check — includes LLM and database status."""
#     llm = check_llm_health()
#     db_ok = is_connected()
#     return {
#         "status": "healthy" if db_ok else "degraded",
#         "version": "2.0.0",
#         "services": {
#             "llm": llm,
#             "database": {
#                 "status": "connected" if db_ok else "disconnected",
#             },
#             "stt": {
#                 "available": STT_AVAILABLE,
#                 "provider": LLM_PROVIDER,
#                 "api_key_set": bool(LLM_API_KEY),
#             },
#         },
#     }
