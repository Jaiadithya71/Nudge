"""
auth.py — JWT creation and verification utilities.

Token payload:
    sub  : user_id (str)
    exp  : expiry timestamp (UTC)
    iat  : issued-at timestamp (UTC)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()

_SECRET      = os.environ.get("JWT_SECRET_KEY", "changeme")
_ALGORITHM   = "HS256"
_TTL_HOURS   = 24


def create_token(user_id: str) -> str:
    """Create a signed JWT for *user_id*, valid for 24 hours."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(hours=_TTL_HOURS),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> str:
    """
    Decode and verify *token*. Returns the user_id (sub claim).
    Raises jose.JWTError on invalid or expired tokens.
    """
    payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise JWTError("Token missing subject claim")
    return user_id
