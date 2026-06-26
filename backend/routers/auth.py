"""
Auth router

Endpoints:
  POST /api/auth/login          — issue access + refresh token
  POST /api/auth/signup         — create account + issue tokens
  GET  /api/auth/me             — current user from access token
  POST /api/auth/refresh        — rotate refresh token, issue new access token
  POST /api/auth/logout         — revoke session (this device)
  POST /api/auth/logout-all     — revoke all sessions (all devices)
  POST /api/auth/reset-password — change password (requires current password)
"""

import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException, status

from auth.dependencies import get_admin_user, get_current_user
from auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from models.requests import (
    AssignOrgRequest,
    LoginRequest,
    PasswordResetRequest,
    RefreshRequest,
    SignupRequest,
)
from services import user_service, session_service
from auth.password_utils import verify_password

router = APIRouter()
logger = logging.getLogger("voxa.router.auth")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _issue_tokens(user: dict, remember_me: bool) -> dict:
    """Create a session, sign both tokens, return the full auth response."""
    logger.info(
        "Issuing auth tokens: user_id_present=%s remember_me=%s",
        bool(user.get("id")),
        remember_me,
    )
    token_id, expires_at = await session_service.create_session(
        user_id=user["id"],
        user_email=user["email"],
        remember_me=remember_me,
    )
    access_token = create_access_token({
        "sub":      user["email"],
        "id":       user["id"],
        "email":    user.get("email"),
        "name":     user.get("name"),
        "username": user.get("username"),
        "role":     user.get("role"),
        "org_id":   user.get("org_id"),
        "is_admin": user.get("is_admin", False),
    })
    refresh_token = create_refresh_token(token_id, user["email"], expires_at)
    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "bearer",
        "remember_me":   remember_me,
        "user":          user,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest):
    """
    Authenticate with username/email + password.
    Returns an access token (60 min) and a refresh token.
    remember_me=True → refresh token lives 30 days instead of 1 day.
    """
    logger.info("Login attempt: remember_me=%s", body.remember_me)
    user = await user_service.authenticate_user(body.username, body.password)
    if not user:
        logger.warning("Login failed: reason=invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    logger.info("Login success: user_id_present=%s", bool(user.get("id")))
    return await _issue_tokens(user, body.remember_me)


@router.post("/signup")
async def signup(body: SignupRequest):
    """Create a new account and return tokens immediately (no separate login step)."""
    try:
        logger.info("Signup attempt")
        user = await user_service.create_user(
            name=body.name,
            username=body.username,
            email=body.email,
            plain_password=body.password,
        )
    except ValueError as exc:
        logger.warning("Signup failed: reason=%s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.info("Signup success: user_id_present=%s", bool(user.get("id")))
    return await _issue_tokens(user, body.remember_me)


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Return the current user's profile from the access token."""
    logger.info("Auth /me: user_id_present=%s", bool(current_user.get("id")))
    return current_user


@router.post("/refresh")
async def refresh(body: RefreshRequest):
    """
    Exchange a valid refresh token for a new access token + rotated refresh token.

    The old refresh token is revoked immediately (rotation) — if a token is
    stolen, the attacker's copy stops working after the legitimate user next
    refreshes.
    """
    try:
        logger.info("Refresh attempt")
        payload = decode_refresh_token(body.refresh_token)
    except jwt.ExpiredSignatureError:
        logger.warning("Refresh failed: expired_refresh_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired — please log in again",
        )
    except jwt.InvalidTokenError:
        logger.warning("Refresh failed: invalid_refresh_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    token_id = payload.get("token_id")
    session = await session_service.get_valid_session(token_id)
    if not session:
        logger.warning("Refresh failed: reason=session_missing_or_revoked")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or revoked — please log in again",
        )

    # Revoke old token (rotation)
    await session_service.revoke_session(token_id)

    # Look up fresh user data
    user = await user_service.get_user_by_login(session["user_email"])
    if not user:
        logger.warning("Refresh failed: reason=user_not_found")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user_public = {k: v for k, v in user.items() if k != "password"}
    logger.info("Refresh success: user_id_present=%s", bool(user_public.get("id")))
    return await _issue_tokens(user_public, session["remember_me"])


@router.post("/logout")
async def logout(body: RefreshRequest):
    """
    Revoke the current device's session.
    Client should discard both tokens after calling this.
    """
    try:
        payload = decode_refresh_token(body.refresh_token)
        await session_service.revoke_session(payload["token_id"])
    except Exception:
        pass   # silently succeed — token may already be expired/revoked
    return {"message": "Logged out"}


# @router.post("/logout-all")
# async def logout_all(current_user: dict = Depends(get_current_user)):
#     """Revoke all active sessions for the current user (logout everywhere)."""
#     await session_service.revoke_all_user_sessions(current_user["id"])
#     return {"message": "Logged out from all devices"}


@router.post("/reset-password")
async def reset_password(body: PasswordResetRequest):
    """
    Change password after verifying the current one.
    Does NOT require an access token — used from the login screen.
    """
    user = await user_service.get_user_by_login(body.identifier)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Verify current password before allowing the change
    stored_hash = user.get("password", "")
    try:
        valid = verify_password(body.old_password, stored_hash)
    except Exception:
        valid = body.old_password == stored_hash   # plain-text fallback for seeded users
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    await user_service.update_password(body.identifier, body.new_password)

    # Revoke all sessions — forces re-login everywhere after a password change
    await session_service.revoke_all_user_sessions(user["id"])

    return {"message": "Password updated. Please log in again."}


# @router.post("/admin/assign-org")
# async def assign_org(
#     body: AssignOrgRequest,
#     admin_user: dict = Depends(get_admin_user),
# ):
#     """
#     Assign a user to an org and optionally grant admin rights.
#     Caller must be an admin; they can only assign users to their own org.
#
#     Bootstrap note: the very first admin must be set directly in MongoDB:
#       db.users.updateOne({email: "..."}, {$set: {org_id: "your-org", is_admin: true}})
#     After that, all subsequent assignments go through this endpoint.
#     """
#     if body.org_id != admin_user["org_id"]:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Admins can only assign users to their own organisation",
#         )
#     await user_service.set_user_org(
#         user_id=body.target_user_id,
#         org_id=body.org_id,
#         is_admin=body.is_admin,
#     )
#     logger.info(
#         "Org assignment: target=%s org=%s is_admin=%s by_admin=%s",
#         body.target_user_id, body.org_id, body.is_admin, admin_user.get("id"),
#     )
#     return {
#         "status": "ok",
#         "target_user_id": body.target_user_id,
#         "org_id": body.org_id,
#         "is_admin": body.is_admin,
#     }
