"""
PoliBrief Backend — Authentication Dependencies (FastAPI)
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.auth.service import decode_access_token, get_admin_by_username
from backend.app.database.session import get_db
from backend.app.models import Administrator

logger = logging.getLogger(__name__)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_admin(
    request: Request,
    db: Session = Depends(get_db),
) -> Administrator:
    """Extract and validate the access token from the httponly cookie."""
    token: Optional[str] = request.cookies.get("pb_access_token")
    if not token:
        raise CREDENTIALS_EXCEPTION

    username = decode_access_token(token)
    if not username:
        raise CREDENTIALS_EXCEPTION

    admin = get_admin_by_username(db, username)
    if not admin:
        raise CREDENTIALS_EXCEPTION

    return admin
