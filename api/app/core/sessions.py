"""Cookie-based server-side sessions."""

from datetime import timedelta

from fastapi import Request, Response
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import as_utc, hash_token, new_token, utcnow
from app.models.user import User, UserSession

SESSION_COOKIE = "bsl_session"
# Throttle last_seen_at writes so every request does not hit the database.
_LAST_SEEN_RESOLUTION = timedelta(seconds=60)


def _client_ip(request: Request) -> str | None:
    return request.client.host[:45] if request.client else None


def create_session(
    db: Session, user: User, request: Request, auth_method: str
) -> str:
    now = utcnow()
    # Opportunistic cleanup of this user's dead sessions.
    db.execute(
        delete(UserSession).where(
            UserSession.user_id == user.id,
            or_(
                UserSession.expires_at < now,
                UserSession.revoked_at.is_not(None),
            ),
        )
    )
    token = new_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            auth_method=auth_method,
            created_at=now,
            last_seen_at=now,
            expires_at=now
            + timedelta(minutes=settings.session_absolute_minutes),
            ip_address=_client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:255]
            or None,
        )
    )
    user.last_login_at = now
    db.commit()
    return token


def resolve_session(db: Session, token: str | None) -> UserSession | None:
    """Return the live session for a raw token, or None."""
    if not token or len(token) > 128:
        return None
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(token))
    )
    if session is None or session.revoked_at is not None:
        return None

    now = utcnow()
    idle_limit = timedelta(minutes=settings.session_idle_minutes)
    if as_utc(session.expires_at) <= now or (
        now - as_utc(session.last_seen_at) > idle_limit
    ):
        session.revoked_at = now
        db.commit()
        return None

    if now - as_utc(session.last_seen_at) > _LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        db.commit()
    return session


def revoke_session(db: Session, session: UserSession) -> None:
    session.revoked_at = utcnow()
    db.commit()


def revoke_all_sessions(db: Session, user: User) -> None:
    now = utcnow()
    for session in user.sessions:
        if session.revoked_at is None:
            session.revoked_at = now
    db.commit()


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_absolute_minutes * 60,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
