"""
Session service — persists refresh tokens in MongoDB.

Each document represents one active "remember this device" session.
A TTL index on expires_at makes MongoDB auto-delete expired sessions.

Rotating refresh tokens:
  Every call to /auth/refresh revokes the old token_id and issues a new one,
  limiting the blast radius if a refresh token is ever stolen.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from config.settings import (
    SESSIONS_COLLECTION,
    REFRESH_TOKEN_EXPIRE_DAYS,
    REFRESH_TOKEN_SHORT_EXPIRE_DAYS,
)
from database.mongodb import get_db

logger = logging.getLogger("voxa.session")

_indexes_created = False


def _col():
    db = get_db()
    if db is None:
        raise RuntimeError("MongoDB not connected")
    return db[SESSIONS_COLLECTION]


async def _ensure_indexes() -> None:
    """Create indexes once per process lifetime."""
    global _indexes_created
    if _indexes_created:
        return
    col = _col()
    await col.create_index("token_id", unique=True)
    # TTL index — MongoDB deletes expired docs automatically
    await col.create_index("expires_at", expireAfterSeconds=0)
    await col.create_index("user_id")
    _indexes_created = True
    logger.info("Session indexes ensured")


async def create_session(
    user_id: str,
    user_email: str,
    remember_me: bool = False,
) -> tuple[str, datetime]:
    """
    Persist a new session.  Returns (token_id, expires_at).

    token_id is embedded in the refresh JWT and looked up on every /refresh call.
    expires_at drives both the JWT exp claim and the MongoDB TTL index.
    """
    await _ensure_indexes()

    token_id = uuid.uuid4().hex
    expire_days = REFRESH_TOKEN_EXPIRE_DAYS if remember_me else REFRESH_TOKEN_SHORT_EXPIRE_DAYS
    expires_at = datetime.now(timezone.utc) + timedelta(days=expire_days)

    await _col().insert_one({
        "token_id":     token_id,
        "user_id":      user_id,
        "user_email":   user_email,
        "remember_me":  remember_me,
        "expires_at":   expires_at,
        "created_at":   datetime.now(timezone.utc),
        "last_used_at": datetime.now(timezone.utc),
        "revoked":      False,
    })
    logger.debug("Session created: remember_me=%s expires=%s", remember_me, expires_at.date())
    return token_id, expires_at


async def get_valid_session(token_id: str) -> Optional[dict]:
    """
    Return the session document if it is active (not revoked, not expired).
    Touches last_used_at on success.
    Returns None if the session is invalid.
    """
    now = datetime.now(timezone.utc)
    session = await _col().find_one({
        "token_id": token_id,
        "revoked":  False,
        "expires_at": {"$gt": now},
    })
    if session:
        await _col().update_one(
            {"token_id": token_id},
            {"$set": {"last_used_at": now}},
        )
    return session


async def revoke_session(token_id: str) -> None:
    """Revoke a single session (single-device logout)."""
    await _col().update_one(
        {"token_id": token_id},
        {"$set": {"revoked": True}},
    )
    logger.debug("Session revoked")


async def revoke_all_user_sessions(user_id: str) -> None:
    """Revoke every session for a user (logout everywhere)."""
    result = await _col().update_many(
        {"user_id": user_id, "revoked": False},
        {"$set": {"revoked": True}},
    )
    logger.info("Revoked sessions: count=%s", result.modified_count)
