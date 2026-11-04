from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.sessions import SESSION_COOKIE, resolve_session
from app.database import get_db
from app.models.user import User, UserSession


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_session(
    request: Request, db: Session = Depends(get_db)
) -> UserSession:
    session = resolve_session(db, request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise _unauthorized("Not signed in or session expired")
    if not session.user.is_active:
        raise _unauthorized("User is not authorized")
    return session


def get_current_user(
    session: UserSession = Depends(get_current_session),
) -> User:
    return session.user


def require_roles(*roles: str) -> Callable[..., User]:
    def role_guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return role_guard
