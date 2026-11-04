"""CSRF protection (double-submit cookie) and security headers.

The SPA's HttpClient reads the non-HttpOnly XSRF-TOKEN cookie and echoes it
in the X-XSRF-TOKEN header on state-changing requests. A cross-site attacker
can make the browser send cookies but cannot read them, so cannot forge the
header.
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.security import new_token, tokens_match

CSRF_COOKIE = "XSRF-TOKEN"
CSRF_HEADER = "X-XSRF-TOKEN"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store",
}


def set_csrf_cookie(response: Response, token: str | None = None) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token or new_token(),
        path="/",
        secure=settings.cookie_secure,
        httponly=False,  # must be readable by the SPA
        samesite="strict",
    )


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        csrf_cookie = request.cookies.get(CSRF_COOKIE)
        is_api = request.url.path.startswith("/api/")

        if is_api and request.method not in SAFE_METHODS:
            if not tokens_match(
                csrf_cookie, request.headers.get(CSRF_HEADER)
            ):
                response: Response = JSONResponse(
                    {"detail": "CSRF token missing or invalid"},
                    status_code=403,
                )
                set_csrf_cookie(response)
                return self._harden(response, is_api)

        response = await call_next(request)
        if not csrf_cookie and not _sets_csrf_cookie(response):
            set_csrf_cookie(response)
        return self._harden(response, is_api)

    @staticmethod
    def _harden(response: Response, is_api: bool) -> Response:
        for name, value in SECURITY_HEADERS.items():
            if name == "Cache-Control" and not is_api:
                continue
            response.headers.setdefault(name, value)
        return response


def _sets_csrf_cookie(response: Response) -> bool:
    """True if the endpoint already issued/rotated the CSRF cookie."""
    prefix = CSRF_COOKIE.encode() + b"="
    return any(
        key.lower() == b"set-cookie" and value.startswith(prefix)
        for key, value in response.raw_headers
    )
