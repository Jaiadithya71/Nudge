import sys
from pathlib import Path
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

# Set up simple logging for the API layer
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── sys.path bridge ────────────────────────────────────────────────────────────
# Adds sibling module directories so core modules are importable without
# installing them as packages.
_API_DIR      = Path(__file__).resolve().parent
_PROJECT_ROOT = _API_DIR.parent

_MODULES = ["Memory", "llm_module", "Remind", "Orchestrator"]

for mod in _MODULES:
    _p = str(_PROJECT_ROOT / mod)
    if _p not in sys.path:
        sys.path.insert(0, _p)

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Auth dependency ────────────────────────────────────────────────────────────

_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """
    FastAPI dependency — validates the Bearer JWT and returns the user_id.

    Usage in a route:
        @router.get("/something")
        def my_route(user_id: str = Depends(get_current_user)):
            ...
    """
    from api.auth import decode_token

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        return decode_token(credentials.credentials)
    except JWTError:
        raise credentials_exception
