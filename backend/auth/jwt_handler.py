"""
JWT creation and decoding — access tokens and refresh tokens.

Access token  (short-lived, 60 min default):
  Signed with JWT_SECRET.  Carries user identity on every request.

Refresh token (long-lived, 1–30 days):
  Signed with REFRESH_TOKEN_SECRET.  Used only at /auth/refresh.
  Contains a token_id that is stored in the sessions collection so it
  can be revoked on logout.  Old token is rotated (invalidated) each
  time a new one is issued.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from config.settings import (
    JWT_SECRET,
    JWT_ALGORITHM,
    REFRESH_TOKEN_SECRET,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)


# ── Access token ──────────────────────────────────────────────────────────────

def create_access_token(payload: dict[str, Any]) -> str:
    """Issue a short-lived access token."""
    data = payload.copy()
    data["type"] = "access"
    data["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate an access token.

    Raises:
        jwt.ExpiredSignatureError  — token has expired
        jwt.InvalidTokenError      — bad signature, wrong type, or malformed
    """
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


# ── Refresh token ─────────────────────────────────────────────────────────────

def create_refresh_token(
    token_id: str,
    user_email: str,
    expires_at: datetime,
) -> str:
    """
    Issue a refresh token.

    token_id  — UUID stored in the sessions collection; used for revocation.
    expires_at — datetime computed by session_service based on remember_me.
    """
    data = {
        "sub": user_email,
        "token_id": token_id,
        "type": "refresh",
        "exp": expires_at,
    }
    return jwt.encode(data, REFRESH_TOKEN_SECRET, algorithm=JWT_ALGORITHM)


def decode_refresh_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a refresh token.

    Raises:
        jwt.ExpiredSignatureError  — token has expired
        jwt.InvalidTokenError      — bad signature, wrong type, or malformed
    """
    payload = jwt.decode(token, REFRESH_TOKEN_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Not a refresh token")
    return payload
