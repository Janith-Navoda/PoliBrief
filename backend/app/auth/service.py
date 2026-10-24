"""
PoliBrief Backend — Authentication Service
Uses Argon2id for password hashing and JWT for session tokens.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models import Administrator

logger = logging.getLogger(__name__)

# Argon2id with conservative parameters
_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

ALGORITHM = "HS256"


# ─── Password Utilities ───────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)


# ─── JWT Utilities ────────────────────────────────────────────────────────────

def create_access_token(subject: str, expire_minutes: Optional[int] = None) -> str:
    minutes = expire_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Returns the subject (username) if valid, else None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ─── Administrator CRUD ───────────────────────────────────────────────────────

def get_admin_by_username(db: Session, username: str) -> Optional[Administrator]:
    return db.query(Administrator).filter(Administrator.username == username).first()


def authenticate_admin(db: Session, username: str, password: str) -> Optional[Administrator]:
    admin = get_admin_by_username(db, username)
    if not admin:
        # Constant-time dummy hash to prevent timing attacks
        hash_password("dummy_constant_time_check")
        return None
    if not verify_password(password, admin.password_hash):
        return None

    # Rehash if parameters have been upgraded
    if password_needs_rehash(admin.password_hash):
        admin.password_hash = hash_password(password)
        db.commit()

    admin.last_login = datetime.now(timezone.utc)
    db.commit()
    logger.info("Administrator '%s' authenticated successfully.", username)
    return admin


def create_admin(db: Session, username: str, password: str) -> Administrator:
    admin = Administrator(
        username=username,
        password_hash=hash_password(password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info("Administrator account '%s' created.", username)
    return admin


def admin_exists(db: Session) -> bool:
    return db.query(Administrator).first() is not None
