"""Google SSO: OpenID Connect authorization-code flow with PKCE.

1. /google/login   -> create state, nonce and PKCE verifier; keep them in a
                      short-lived HttpOnly cookie; redirect to Google.
2. Google          -> user authenticates, Google redirects back with ?code&state
3. /google/callback-> check state against the cookie, exchange the code
                      (client secret + PKCE verifier) for an ID token, verify
                      it (signature, audience, issuer, expiry, nonce, email,
                      domain), then start a normal session.
"""

import base64
import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from fastapi import Response

from app.config import settings
from app.core.security import tokens_match

logger = logging.getLogger(__name__)

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SCOPES = "openid email profile"

FLOW_COOKIE = "bsl_google_flow"
FLOW_COOKIE_PATH = "/api/auth/google"
FLOW_TTL_SECONDS = 600
TOKEN_TIMEOUT_SECONDS = 10
MAX_RETURN_PATH_LENGTH = 2048


class GoogleSSOError(Exception):
    """Carries a short, non-sensitive code shown to the UI via ?error=."""

    def __init__(self, code: str, log_message: str = "") -> None:
        super().__init__(log_message or code)
        self.code = code


# Error codes understood by the UI login page.
ERR_UNAVAILABLE = "google_unavailable"
ERR_CANCELLED = "google_cancelled"
ERR_FAILED = "google_failed"
ERR_NOT_AUTHORIZED = "google_not_authorized"


@dataclass(frozen=True)
class GoogleFlow:
    state: str
    nonce: str
    code_verifier: str
    return_path: str

    def to_cookie(self) -> str:
        raw = json.dumps(
            {
                "s": self.state,
                "n": self.nonce,
                "v": self.code_verifier,
                "r": self.return_path,
            },
            separators=(",", ":"),
        )
        return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    @classmethod
    def from_cookie(cls, value: str | None) -> "GoogleFlow | None":
        if not value or len(value) > 4096:
            return None
        try:
            padded = value + "=" * (-len(value) % 4)
            data = json.loads(base64.urlsafe_b64decode(padded))
            flow = cls(
                state=str(data["s"]),
                nonce=str(data["n"]),
                code_verifier=str(data["v"]),
                return_path=safe_return_path(str(data["r"])),
            )
        except (ValueError, KeyError, TypeError):
            return None
        return flow


def safe_return_path(path: str | None) -> str:
    """Only same-app absolute paths; blocks open redirects like //evil.com."""
    if (
        not path
        or len(path) > MAX_RETURN_PATH_LENGTH
        or not path.startswith("/")
        or path.startswith("//")
        or path.startswith("/\\")
        or any(ord(c) < 0x20 or c == "\x7f" for c in path)
    ):
        return "/"
    if path == "/login" or path.startswith(("/login?", "/login#")):
        return "/"
    return path


def ui_url(path: str) -> str:
    return f"{settings.ui_base}{path}"


def ui_login_error_url(code: str, return_path: str = "/") -> str:
    query = {"error": code}
    if return_path != "/":
        query["returnUrl"] = return_path
    return ui_url(f"/login?{urlencode(query)}")


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def begin(return_path: str | None) -> tuple[str, GoogleFlow]:
    """Return (Google authorization URL, flow state to store in a cookie)."""
    flow = GoogleFlow(
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(32),
        code_verifier=secrets.token_urlsafe(64),  # 86 chars, within 43..128
        return_path=safe_return_path(return_path),
    )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": flow.state,
        "nonce": flow.nonce,
        "code_challenge": _pkce_challenge(flow.code_verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
        "access_type": "online",
    }
    domains = settings.google_allowed_domain_set
    if len(domains) == 1:
        # UI hint only; the hd claim is still enforced on the ID token.
        params["hd"] = next(iter(domains))
    return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}", flow


def set_flow_cookie(response: Response, flow: GoogleFlow) -> None:
    response.set_cookie(
        FLOW_COOKIE,
        flow.to_cookie(),
        max_age=FLOW_TTL_SECONDS,
        path=FLOW_COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        # Lax (not Strict) is required: the callback is a top-level
        # navigation arriving from accounts.google.com.
        samesite="lax",
    )


def clear_flow_cookie(response: Response) -> None:
    response.delete_cookie(
        FLOW_COOKIE,
        path=FLOW_COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def check_state(flow: GoogleFlow | None, state: str | None) -> GoogleFlow:
    if flow is None or not tokens_match(flow.state, state):
        raise GoogleSSOError(ERR_FAILED, "OAuth state missing or mismatched")
    return flow


def exchange_code(code: str, flow: GoogleFlow) -> str:
    """Exchange the authorization code for a Google ID token."""
    if not code or len(code) > 2048:
        raise GoogleSSOError(ERR_FAILED, "Missing or oversized authorization code")
    if not settings.google_sso_enabled or settings.google_client_secret is None:
        raise GoogleSSOError(ERR_UNAVAILABLE, "Google SSO is not configured")
    try:
        response = requests.post(
            TOKEN_ENDPOINT,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.google_redirect_uri,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value(),
                "code_verifier": flow.code_verifier,
            },
            headers={"Accept": "application/json"},
            timeout=TOKEN_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise GoogleSSOError(ERR_UNAVAILABLE, f"Token endpoint unreachable: {exc}") from exc

    if response.status_code != 200:
        # Google's error body has no secrets; log only the error code.
        try:
            error = response.json().get("error", "unknown")
        except ValueError:
            error = "unparseable"
        raise GoogleSSOError(
            ERR_FAILED, f"Token exchange failed: HTTP {response.status_code} {error}"
        )
    try:
        id_token = response.json()["id_token"]
    except (ValueError, KeyError, TypeError) as exc:
        raise GoogleSSOError(ERR_FAILED, "Token response had no id_token") from exc
    if not isinstance(id_token, str) or not id_token:
        raise GoogleSSOError(ERR_FAILED, "Token response had an invalid id_token")
    return id_token
