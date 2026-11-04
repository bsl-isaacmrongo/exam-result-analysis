from datetime import timedelta
from typing import Any

import google.auth.exceptions
from fastapi import HTTPException, status
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    as_utc,
    hash_password,
    tokens_match,
    utcnow,
    verify_password,
)
from app.models.user import User

INVALID_CREDENTIALS = "Invalid email or password"
ACCOUNT_LOCKED = (
    "Too many failed sign-in attempts. Please try again in a few minutes."
)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User).where(func.lower(User.email) == normalize_email(email))
    )


# --------------------------------------------------------------------------
# Password sign-in
# --------------------------------------------------------------------------


def authenticate_password(db: Session, email: str, password: str) -> User:
    user = find_user_by_email(db, email)
    now = utcnow()

    usable = user is not None and user.is_active and user.password_hash
    # Always run argon2 so timing doesn't reveal whether the account exists.
    valid, needs_rehash = verify_password(
        user.password_hash if usable else None, password
    )

    if not usable:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
        )

    if user.locked_until and as_utc(user.locked_until) > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ACCOUNT_LOCKED,
        )

    if not valid:
        attempts = (user.failed_login_attempts or 0) + 1
        if attempts >= settings.login_max_attempts:
            user.locked_until = now + timedelta(
                minutes=settings.login_lockout_minutes
            )
            attempts = 0
        user.failed_login_attempts = attempts
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    if needs_rehash:
        user.password_hash = hash_password(password)
    db.commit()
    return user


# --------------------------------------------------------------------------
# Google sign-in
# --------------------------------------------------------------------------


def verify_google_id_token(
    encoded_token: str, expected_nonce: str | None
) -> dict[str, Any]:
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )

    try:
        # Checks signature, issuer (accounts.google.com), expiry and audience.
        claims = id_token.verify_oauth2_token(
            encoded_token,
            Request(),
            audience=settings.google_client_id,
            clock_skew_in_seconds=10,
        )
    except google.auth.exceptions.TransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google token verification is temporarily unavailable",
        ) from exc
    except (ValueError, google.auth.exceptions.GoogleAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
        ) from exc

    # Binds the ID token to the login attempt that started in this browser.
    if not tokens_match(claims.get("nonce"), expected_nonce):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google sign-in request expired. Please try again.",
        )
    if claims.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is not verified",
        )
    if not claims.get("sub") or not claims.get("email"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID token is missing required account details",
        )
    allowed = settings.google_allowed_domain_set
    if allowed and str(claims.get("hd", "")).casefold() not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please sign in with your school Google account",
        )
    return claims


def get_provisioned_user(db: Session, claims: dict[str, Any]) -> User:
    google_sub = claims["sub"]
    email = normalize_email(claims["email"])
    not_granted = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This Google account has not been granted access",
    )

    user = db.scalar(select(User).where(User.google_sub == google_sub))
    if user is None:
        user = find_user_by_email(db, email)
        if user is None or (user.google_sub and user.google_sub != google_sub):
            raise not_granted
        if user.is_active:
            # First Google sign-in: link to Google's stable subject ID.
            user.google_sub = google_sub
            if not user.name and claims.get("name"):
                user.name = claims["name"]
            db.commit()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is disabled",
        )
    return user
