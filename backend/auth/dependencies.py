"""
FastAPI dependency for JWT authentication.
Extracts and validates the Bearer token from the Authorization header.
"""

import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_handler import decode_access_token

logger = logging.getLogger("voxa.auth")

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    Resolve the current user from a JWT Bearer token in the Authorization header.
    Raises HTTP 401 if no valid token is present.
    """
    raw = credentials.credentials if credentials else None
    if not raw:
        logger.warning("Auth failed: missing bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(raw)
        logger.info(
            "Auth success: user_id_present=%s token_source=%s",
            bool(payload.get("id")),
            "header",
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Auth failed: expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning(f"Auth failed: invalid token: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Require the current user to be an org admin (is_admin=True and org_id set).
    Raises HTTP 403 if they are not.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    if not current_user.get("org_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to an organisation",
        )
    return current_user
