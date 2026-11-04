"""Password hashing and opaque token helpers."""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# argon2id with the library's RFC 9106 defaults.
_password_hasher = PasswordHasher()

# Verified against when the account is unknown or has no password, so that
# response timing does not reveal which email addresses exist.
_DUMMY_PASSWORD_HASH = _password_hasher.hash(secrets.token_urlsafe(32))

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Treat naive datetimes (e.g. from SQLite) as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def validate_password_strength(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must be at most {PASSWORD_MAX_LENGTH} characters"
        )
    if password.strip() != password or not password.strip():
        raise ValueError("Password must not start or end with whitespace")


def hash_password(password: str) -> str:
    validate_password_strength(password)
    return _password_hasher.hash(password)


def verify_password(
    password_hash: str | None, password: str
) -> tuple[bool, bool]:
    """Return (is_valid, needs_rehash). Always does the same amount of work."""
    try:
        _password_hasher.verify(
            password_hash or _DUMMY_PASSWORD_HASH, password
        )
    except (VerificationError, InvalidHashError):
        return False, False
    if password_hash is None:
        return False, False
    return True, _password_hasher.check_needs_rehash(password_hash)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
