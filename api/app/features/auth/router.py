import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.dependencies import get_current_user
from app.core.middleware import set_csrf_cookie
from app.core.sessions import (
    SESSION_COOKIE,
    clear_session_cookie,
    create_session,
    resolve_session,
    revoke_session,
    set_session_cookie,
)
from app.database import get_db
from app.features.auth import google_sso
from app.features.auth.schemas import (
    AuthOptionsResponse,
    PasswordLoginRequest,
    UserResponse,
)
from app.features.auth.service import (
    authenticate_password,
    get_provisioned_user,
    verify_google_id_token,
)
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _start_session(
    db: Session, user: User, request: Request, response: Response, method: str
) -> User:
    token = create_session(db, user, request, method)
    set_session_cookie(response, token)
    # Rotate the CSRF token at the privilege boundary.
    set_csrf_cookie(response)
    return user


@router.get("/options", response_model=AuthOptionsResponse)
def auth_options() -> AuthOptionsResponse:
    """Public login-page config."""
    return AuthOptionsResponse(google_enabled=settings.google_sso_enabled)


@router.post("/login", response_model=UserResponse)
def password_login(
    payload: PasswordLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    user = authenticate_password(db, payload.email, payload.password)
    return _start_session(db, user, request, response, "password")


@router.get("/google/login", include_in_schema=True)
def google_sso_login(
    return_url: str | None = Query(default=None, max_length=2048),
) -> RedirectResponse:
    """Browser navigates here; we redirect to Google's consent screen."""
    if not settings.google_sso_enabled:
        return RedirectResponse(
            google_sso.ui_login_error_url(google_sso.ERR_UNAVAILABLE),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    authorization_url, flow = google_sso.begin(return_url)
    response = RedirectResponse(authorization_url, status_code=status.HTTP_303_SEE_OTHER)
    google_sso.set_flow_cookie(response, flow)
    return response


@router.get("/google/callback", include_in_schema=True)
def google_sso_callback(
    request: Request,
    code: str | None = Query(default=None, max_length=2048),
    state: str | None = Query(default=None, max_length=512),
    error: str | None = Query(default=None, max_length=256),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Google redirects here. Always ends with a redirect back to the UI."""
    flow = google_sso.GoogleFlow.from_cookie(
        request.cookies.get(google_sso.FLOW_COOKIE)
    )
    return_path = flow.return_path if flow else "/"

    try:
        if error:
            code_ = (
                google_sso.ERR_CANCELLED
                if error == "access_denied"
                else google_sso.ERR_FAILED
            )
            raise google_sso.GoogleSSOError(code_, f"Google returned error={error!r}")
        if not settings.google_sso_enabled:
            raise google_sso.GoogleSSOError(google_sso.ERR_UNAVAILABLE)
        flow = google_sso.check_state(flow, state)
        id_token = google_sso.exchange_code(code or "", flow)
        try:
            claims = verify_google_id_token(id_token, flow.nonce)
            user = get_provisioned_user(db, claims)
        except HTTPException as exc:
            code_ = {
                status.HTTP_403_FORBIDDEN: google_sso.ERR_NOT_AUTHORIZED,
                status.HTTP_503_SERVICE_UNAVAILABLE: google_sso.ERR_UNAVAILABLE,
            }.get(exc.status_code, google_sso.ERR_FAILED)
            raise google_sso.GoogleSSOError(code_, str(exc.detail)) from exc
    except google_sso.GoogleSSOError as exc:
        logger.warning("Google SSO failed (%s): %s", exc.code, exc)
        response = RedirectResponse(
            google_sso.ui_login_error_url(exc.code, return_path),
            status_code=status.HTTP_303_SEE_OTHER,
        )
        google_sso.clear_flow_cookie(response)
        return response

    response = RedirectResponse(
        google_sso.ui_url(flow.return_path), status_code=status.HTTP_303_SEE_OTHER
    )
    google_sso.clear_flow_cookie(response)  # state/nonce/verifier are single-use
    _start_session(db, user, request, response, "google")
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> None:
    """Idempotent: always clears the cookie, revokes the session if live."""
    session = resolve_session(db, request.cookies.get(SESSION_COOKIE))
    if session is not None:
        revoke_session(db, session)
    clear_session_cookie(response)
    set_csrf_cookie(response)


@router.get("/me", response_model=UserResponse)
def read_current_user(user: User = Depends(get_current_user)) -> User:
    return user
