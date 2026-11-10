import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from .config import get_settings

_ph = PasswordHasher()


def hash_password(p: str) -> str:
    return _ph.hash(p)


def verify_password(p: str, h: str) -> bool:
    try:
        return _ph.verify(h, p)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_token(user_id: int, kind: str, minutes: int) -> str:
    s = get_settings()
    payload = {"sub": str(user_id), "kind": kind, "iat": _now(), "exp": _now() + timedelta(minutes=minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str, kind: str) -> int | None:
    try:
        data = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if data.get("kind") != kind:
        return None
    try:
        return int(data["sub"])
    except (KeyError, ValueError):
        return None


def random_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()
