"""
PoliBrief Backend — Authentication API Router
Endpoints: login, logout, status, setup (first-run admin creation)
"""
import logging
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_admin
from backend.app.auth.service import (
    admin_exists,
    authenticate_admin,
    create_admin,
    get_admin_by_username,
)
from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.models import Administrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Simple in-memory rate limiter per IP
_login_attempts: dict[str, list[float]] = {}
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300  # 5 minutes


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    # Purge attempts outside the window
    attempts = [t for t in attempts if now - t < WINDOW_SECONDS]
    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait 5 minutes.",
        )
    attempts.append(now)
    _login_attempts[ip] = attempts


# ─── Schemas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=10, max_length=256)


class AdminOut(BaseModel):
    id: int
    username: str

    model_config = {"from_attributes": True}


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    admin = authenticate_admin(db, payload.username, payload.password)
    if not admin:
        logger.warning("Failed login attempt for username='%s' from %s", payload.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    from backend.app.auth.service import create_access_token
    token = create_access_token(admin.username)

    # Set secure httponly cookie — SameSite=Lax is safe for localhost SPA
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="pb_access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=max_age,
        path="/",
    )

    return {"detail": "Login successful", "username": admin.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("pb_access_token", path="/")
    return {"detail": "Logged out successfully."}


@router.get("/me", response_model=AdminOut)
def me(current: Administrator = Depends(get_current_admin)):
    return current


@router.get("/status")
def auth_status(request: Request, db: Session = Depends(get_db)):
    """Returns setup state and auth state — used by the frontend on boot."""
    setup_done = admin_exists(db)
    token = request.cookies.get("pb_access_token")
    authenticated = False
    username = None

    if token:
        from backend.app.auth.service import decode_access_token
        uname = decode_access_token(token)
        if uname and get_admin_by_username(db, uname):
            authenticated = True
            username = uname

    return {
        "setup_complete": setup_done,
        "authenticated": authenticated,
        "username": username,
    }


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(payload: SetupRequest, db: Session = Depends(get_db)):
    """First-run endpoint to create the initial administrator account.
    Disabled once any administrator exists.
    """
    if admin_exists(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrator account already exists.",
        )

    admin = create_admin(db, payload.username, payload.password)
    logger.info("Initial administrator setup completed for '%s'.", payload.username)
    return {"detail": "Administrator account created.", "username": admin.username}
