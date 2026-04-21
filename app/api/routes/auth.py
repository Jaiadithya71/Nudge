"""
auth.py — Authentication routes.

POST /api/auth/login  — exchange user_id + password for a JWT
GET  /api/auth/me     — verify token and return the current user_id
"""

import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import create_token
from api.dependencies import get_current_user
from api.schemas.base import LoginRequest, TokenResponse

load_dotenv()

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    """
    Issue a JWT for *user_id* if *password* matches APP_PASSWORD.

    The user_id is caller-supplied — it becomes the token subject and
    determines which isolated memory store is accessed.
    """
    expected = os.environ.get("APP_PASSWORD", "")
    if not expected or payload.password != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_token(payload.user_id)
    return TokenResponse(access_token=token, user_id=payload.user_id)


@router.get("/me")
def me(user_id: str = Depends(get_current_user)):
    """Return the user_id encoded in the current token."""
    return {"user_id": user_id}
