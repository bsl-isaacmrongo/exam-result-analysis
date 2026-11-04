import unittest
from urllib.parse import parse_qs, urlparse
from datetime import timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.middleware import CSRF_COOKIE, CSRF_HEADER
from app.core.security import hash_password, utcnow, verify_password
from app.core.sessions import SESSION_COOKIE
from app.database import get_db
from app.features.auth import google_sso
from app.features.auth.service import (
    get_provisioned_user,
    verify_google_id_token,
)
from app.main import app
from app.models.base import Base
from app.models.user import User, UserSession

PASSWORD = "correct horse battery staple"


class AuthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        def override_get_db():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app, base_url="https://testserver")

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_db, None)
        self.db.close()
        self.engine.dispose()

    def add_user(self, **kwargs) -> User:
        user = User(
            email=kwargs.pop("email", "staff@example.org"),
            failed_login_attempts=0,
            **kwargs,
        )
        self.db.add(user)
        self.db.commit()
        return user

    def csrf(self) -> dict[str, str]:
        if CSRF_COOKIE not in self.client.cookies:
            self.client.get("/health")
        return {CSRF_HEADER: self.client.cookies[CSRF_COOKIE]}

    def password_login(self, password: str = PASSWORD, email="staff@example.org"):
        return self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            headers=self.csrf(),
        )


class PasswordHashingTests(unittest.TestCase):
    def test_hash_round_trip(self) -> None:
        hashed = hash_password(PASSWORD)
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertEqual(verify_password(hashed, PASSWORD), (True, False))
        self.assertEqual(verify_password(hashed, "wrong")[0], False)

    def test_missing_hash_never_verifies(self) -> None:
        self.assertEqual(verify_password(None, PASSWORD), (False, False))

    def test_weak_password_rejected(self) -> None:
        with self.assertRaises(ValueError):
            hash_password("short")


class PasswordLoginTests(AuthTestCase):
    def test_login_sets_httponly_session_and_me_works(self) -> None:
        self.add_user(password_hash=hash_password(PASSWORD), name="Staff")

        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        response = self.password_login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "staff@example.org")
        self.assertNotIn("password_hash", response.json())

        set_cookie = "; ".join(response.headers.get_list("set-cookie"))
        self.assertIn(f"{SESSION_COOKIE}=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=strict", set_cookie)
        self.assertIn("Secure", set_cookie)

        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["name"], "Staff")

    def test_email_is_case_insensitive(self) -> None:
        self.add_user(password_hash=hash_password(PASSWORD))
        response = self.password_login(email="  STAFF@Example.org ")
        self.assertEqual(response.status_code, 200)

    def test_wrong_password_and_unknown_user_look_identical(self) -> None:
        self.add_user(password_hash=hash_password(PASSWORD))
        wrong = self.password_login("not the password!!")
        unknown = self.password_login(email="nobody@example.org")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.json(), unknown.json())

    def test_google_only_and_inactive_accounts_cannot_use_password(self) -> None:
        self.add_user(email="google@example.org")
        self.add_user(
            email="off@example.org",
            password_hash=hash_password(PASSWORD),
            is_active=False,
        )
        self.assertEqual(
            self.password_login(email="google@example.org").status_code, 401
        )
        self.assertEqual(
            self.password_login(email="off@example.org").status_code, 401
        )

    def test_account_locks_after_repeated_failures(self) -> None:
        self.add_user(password_hash=hash_password(PASSWORD))
        with patch("app.features.auth.service.settings.login_max_attempts", 3):
            for _ in range(3):
                self.assertEqual(self.password_login("wrong-password!").status_code, 401)
            # Even the right password is refused while locked.
            self.assertEqual(self.password_login().status_code, 429)

    def test_successful_login_resets_failure_counter(self) -> None:
        user = self.add_user(password_hash=hash_password(PASSWORD))
        self.password_login("wrong-password!")
        self.assertEqual(self.password_login().status_code, 200)
        self.db.refresh(user)
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertIsNotNone(user.last_login_at)


class CsrfTests(AuthTestCase):
    def test_post_without_csrf_header_is_rejected(self) -> None:
        self.add_user(password_hash=hash_password(PASSWORD))
        self.client.get("/health")
        response = self.client.post(
            "/api/auth/login",
            json={"email": "staff@example.org", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 403)

    def test_post_with_mismatched_csrf_header_is_rejected(self) -> None:
        self.client.get("/health")
        response = self.client.post(
            "/api/auth/logout", headers={CSRF_HEADER: "forged"}
        )
        self.assertEqual(response.status_code, 403)

    def test_csrf_token_rotates_on_login(self) -> None:
        self.add_user(password_hash=hash_password(PASSWORD))
        before = self.csrf()[CSRF_HEADER]
        self.password_login()
        self.assertNotEqual(self.client.cookies[CSRF_COOKIE], before)


class SessionTests(AuthTestCase):
    def test_logout_revokes_session_server_side(self) -> None:
        self.add_user(password_hash=hash_password(PASSWORD))
        self.password_login()
        token = self.client.cookies[SESSION_COOKIE]

        self.assertEqual(
            self.client.post("/api/auth/logout", headers=self.csrf()).status_code,
            204,
        )
        # Replaying the old cookie must not work.
        self.client.cookies.set(SESSION_COOKIE, token)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_logout_without_session_is_idempotent(self) -> None:
        response = self.client.post("/api/auth/logout", headers=self.csrf())
        self.assertEqual(response.status_code, 204)

    def test_expired_and_idle_sessions_are_rejected(self) -> None:
        self.add_user(password_hash=hash_password(PASSWORD))
        for field, delta in (
            ("expires_at", timedelta(seconds=-1)),
            ("last_seen_at", timedelta(days=-1)),
        ):
            self.password_login()
            session = self.db.scalars(
                select(UserSession).order_by(UserSession.id.desc())
            ).first()
            setattr(session, field, utcnow() + delta)
            self.db.commit()
            self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_disabled_user_loses_access_immediately(self) -> None:
        user = self.add_user(password_hash=hash_password(PASSWORD))
        self.password_login()
        user.is_active = False
        self.db.commit()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_only_token_hash_is_stored(self) -> None:
        self.add_user(password_hash=hash_password(PASSWORD))
        self.password_login()
        token = self.client.cookies[SESSION_COOKIE]
        stored = self.db.scalars(select(UserSession.token_hash)).all()
        self.assertEqual(len(stored), 1)
        self.assertNotEqual(stored[0], token)

    def test_security_headers_present(self) -> None:
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["cache-control"], "no-store")


class CorsTests(AuthTestCase):
    def test_ui_origin_is_allowed_with_credentials(self) -> None:
        response = self.client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:4200",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-xsrf-token",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"], "http://localhost:4200"
        )
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")

    def test_other_origins_are_not_allowed(self) -> None:
        response = self.client.get(
            "/api/auth/me", headers={"Origin": "https://evil.example"}
        )
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_csrf_rejection_still_carries_cors_headers(self) -> None:
        response = self.client.post(
            "/api/auth/logout", headers={"Origin": "http://localhost:4200"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.headers["access-control-allow-origin"], "http://localhost:4200"
        )


GOOGLE_CLAIMS = {
    "sub": "google-user-id",
    "email": "staff@example.org",
    "email_verified": True,
    "name": "Staff Member",
}


class GoogleTokenTests(unittest.TestCase):
    def verify(self, claims, nonce="n-1", **settings_overrides):
        with (
            patch("app.features.auth.service.settings.google_client_id", "cid"),
            patch(
                "app.features.auth.service.settings.google_allowed_domains",
                settings_overrides.get("domains", ""),
            ),
            patch(
                "app.features.auth.service.id_token.verify_oauth2_token",
                return_value=claims,
            ) as verify,
        ):
            result = verify_google_id_token("google-id-token", nonce)
        self.assertEqual(verify.call_args.kwargs["audience"], "cid")
        return result

    def test_valid_token(self) -> None:
        claims = {**GOOGLE_CLAIMS, "nonce": "n-1"}
        self.assertEqual(self.verify(claims), claims)

    def test_nonce_must_match(self) -> None:
        for nonce in ("other", None):
            with self.assertRaises(HTTPException) as raised:
                self.verify({**GOOGLE_CLAIMS, "nonce": "n-1"}, nonce=nonce)
            self.assertEqual(raised.exception.status_code, 401)

    def test_requires_verified_email(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            self.verify({**GOOGLE_CLAIMS, "nonce": "n-1", "email_verified": False})
        self.assertEqual(raised.exception.status_code, 401)

    def test_hosted_domain_restriction(self) -> None:
        claims = {**GOOGLE_CLAIMS, "nonce": "n-1", "hd": "school.org"}
        self.assertEqual(self.verify(claims, domains="school.org"), claims)
        with self.assertRaises(HTTPException) as raised:
            self.verify({**GOOGLE_CLAIMS, "nonce": "n-1"}, domains="school.org")
        self.assertEqual(raised.exception.status_code, 403)

    def test_not_configured(self) -> None:
        with patch("app.features.auth.service.settings.google_client_id", None):
            with self.assertRaises(HTTPException) as raised:
                verify_google_id_token("t", "n")
        self.assertEqual(raised.exception.status_code, 503)


class GoogleProvisioningTests(AuthTestCase):
    def test_preprovisioned_user_is_linked_by_verified_email(self) -> None:
        user = self.add_user()
        authenticated = get_provisioned_user(
            self.db, {**GOOGLE_CLAIMS, "email": "STAFF@example.org"}
        )
        self.assertEqual(authenticated.id, user.id)
        self.assertEqual(authenticated.google_sub, "google-user-id")
        self.assertEqual(authenticated.name, "Staff Member")

    def test_unprovisioned_google_account_is_denied(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            get_provisioned_user(
                self.db, {**GOOGLE_CLAIMS, "email": "unknown@example.org"}
            )
        self.assertEqual(raised.exception.status_code, 403)

    def test_inactive_user_is_denied_and_not_linked(self) -> None:
        user = self.add_user(is_active=False)
        with self.assertRaises(HTTPException) as raised:
            get_provisioned_user(self.db, GOOGLE_CLAIMS)
        self.assertEqual(raised.exception.status_code, 403)
        self.db.refresh(user)
        self.assertIsNone(user.google_sub)

    def test_linked_google_account_cannot_be_replaced(self) -> None:
        self.add_user(google_sub="original-sub")
        with self.assertRaises(HTTPException) as raised:
            get_provisioned_user(self.db, {**GOOGLE_CLAIMS, "sub": "different"})
        self.assertEqual(raised.exception.status_code, 403)

    def test_unprovisioned_user_is_not_linked_by_failed_attempt(self) -> None:
        with self.assertRaises(HTTPException):
            get_provisioned_user(self.db, GOOGLE_CLAIMS)
        self.assertIsNone(self.db.scalar(select(User)))


class FakeTokenResponse:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


SSO_SETTINGS = {
    "google_client_id": "cid.apps.googleusercontent.com",
    "google_client_secret": "test-secret",
    "google_redirect_uri": "https://testserver/api/auth/google/callback",
    "ui_base_url": "http://ui.test",
    "google_allowed_domains": "",
}


class GoogleSSOTests(AuthTestCase):
    def setUp(self) -> None:
        super().setUp()
        from pydantic import SecretStr

        from app.config import settings

        self.patches = [
            patch.object(
                settings,
                key,
                SecretStr(value) if key == "google_client_secret" else value,
            )
            for key, value in SSO_SETTINGS.items()
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self.patches):
            p.stop()
        super().tearDown()

    def start(self, return_url: str | None = "/reports?year=2026"):
        params = {"return_url": return_url} if return_url is not None else {}
        response = self.client.get(
            "/api/auth/google/login", params=params, follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        location = urlparse(response.headers["location"])
        return response, location, {k: v[0] for k, v in parse_qs(location.query).items()}

    def callback(self, **params):
        return self.client.get(
            "/api/auth/google/callback", params=params, follow_redirects=False
        )

    def complete(self, claims_override=None, token_response=None, state=None):
        _, _, query = self.start()
        flow = google_sso.GoogleFlow.from_cookie(
            self.client.cookies[google_sso.FLOW_COOKIE]
        )
        claims = {**GOOGLE_CLAIMS, "nonce": flow.nonce, **(claims_override or {})}
        with (
            patch(
                "app.features.auth.google_sso.requests.post",
                return_value=token_response
                or FakeTokenResponse(200, {"id_token": "google-id-token"}),
            ) as post,
            patch(
                "app.features.auth.service.id_token.verify_oauth2_token",
                return_value=claims,
            ),
        ):
            response = self.callback(code="auth-code", state=state or query["state"])
        return response, post, flow

    def test_options_reports_google_enabled(self) -> None:
        self.assertTrue(self.client.get("/api/auth/options").json()["google_enabled"])
        with patch("app.config.settings.google_client_secret", None):
            self.assertFalse(
                self.client.get("/api/auth/options").json()["google_enabled"]
            )

    def test_login_redirects_to_google_with_pkce_state_and_nonce(self) -> None:
        response, location, query = self.start()
        self.assertEqual(
            f"{location.scheme}://{location.netloc}{location.path}",
            google_sso.AUTHORIZATION_ENDPOINT,
        )
        self.assertEqual(query["client_id"], SSO_SETTINGS["google_client_id"])
        self.assertEqual(query["redirect_uri"], SSO_SETTINGS["google_redirect_uri"])
        self.assertEqual(query["response_type"], "code")
        self.assertEqual(query["code_challenge_method"], "S256")
        self.assertIn("openid", query["scope"])
        self.assertNotIn("test-secret", response.headers["location"])

        flow = google_sso.GoogleFlow.from_cookie(
            self.client.cookies[google_sso.FLOW_COOKIE]
        )
        self.assertEqual(flow.state, query["state"])
        self.assertEqual(flow.nonce, query["nonce"])
        self.assertEqual(
            google_sso._pkce_challenge(flow.code_verifier), query["code_challenge"]
        )
        self.assertEqual(flow.return_path, "/reports?year=2026")

        set_cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=lax", set_cookie)
        self.assertIn("Path=/api/auth/google", set_cookie)

    def test_login_when_not_configured_bounces_to_ui(self) -> None:
        with patch("app.config.settings.google_client_secret", None):
            response = self.client.get(
                "/api/auth/google/login", follow_redirects=False
            )
        self.assertEqual(
            response.headers["location"],
            "http://ui.test/login?error=google_unavailable",
        )

    def test_open_redirects_are_neutralised(self) -> None:
        for bad in ("//evil.com", "https://evil.com", "/\\evil.com", "/login", "x"):
            self.start(bad)
            flow = google_sso.GoogleFlow.from_cookie(
                self.client.cookies[google_sso.FLOW_COOKIE]
            )
            self.assertEqual(flow.return_path, "/", bad)

    def test_successful_callback_creates_session_and_returns_to_ui(self) -> None:
        self.add_user()
        response, post, flow = self.complete()

        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            response.headers["location"], "http://ui.test/reports?year=2026"
        )
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent["code"], "auth-code")
        self.assertEqual(sent["code_verifier"], flow.code_verifier)
        self.assertEqual(sent["client_secret"], "test-secret")
        self.assertEqual(sent["grant_type"], "authorization_code")
        self.assertEqual(post.call_args.kwargs["timeout"], google_sso.TOKEN_TIMEOUT_SECONDS)

        self.assertNotIn(google_sso.FLOW_COOKIE, self.client.cookies)
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "staff@example.org")
        session = self.db.scalar(select(UserSession))
        self.assertEqual(session.auth_method, "google")

    def test_state_mismatch_is_rejected_without_token_exchange(self) -> None:
        self.add_user()
        response, post, _ = self.complete(state="forged-state")
        self.assertIn("error=google_failed", response.headers["location"])
        post.assert_not_called()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_callback_without_flow_cookie_is_rejected(self) -> None:
        response = self.callback(code="auth-code", state="anything")
        self.assertEqual(
            response.headers["location"], "http://ui.test/login?error=google_failed"
        )

    def test_flow_cookie_is_cleared_after_success_and_failure(self) -> None:
        # Single use: the browser drops state/nonce/verifier after one callback
        # (and Google itself rejects a reused authorization code).
        self.add_user()
        self.complete()
        self.assertNotIn(google_sso.FLOW_COOKIE, self.client.cookies)

        response, _, _ = self.complete(state="forged-state")
        self.assertIn("error=", response.headers["location"])
        self.assertNotIn(google_sso.FLOW_COOKIE, self.client.cookies)

    def test_user_cancelling_at_google(self) -> None:
        self.start()
        response = self.callback(error="access_denied", state="x")
        self.assertIn("error=google_cancelled", response.headers["location"])
        self.assertIn("returnUrl=%2Freports", response.headers["location"])

    def test_failed_code_exchange(self) -> None:
        self.add_user()
        response, _, _ = self.complete(
            token_response=FakeTokenResponse(400, {"error": "invalid_grant"})
        )
        self.assertIn("error=google_failed", response.headers["location"])
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_token_endpoint_unreachable(self) -> None:
        import requests

        self.add_user()
        _, _, query = self.start()
        with patch(
            "app.features.auth.google_sso.requests.post",
            side_effect=requests.ConnectionError("down"),
        ):
            response = self.callback(code="auth-code", state=query["state"])
        self.assertIn("error=google_unavailable", response.headers["location"])

    def test_nonce_mismatch_is_rejected(self) -> None:
        self.add_user()
        response, _, _ = self.complete({"nonce": "attacker-nonce"})
        self.assertIn("error=google_failed", response.headers["location"])
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_unprovisioned_account_is_not_authorized(self) -> None:
        response, _, _ = self.complete({"email": "stranger@example.org"})
        self.assertIn("error=google_not_authorized", response.headers["location"])
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_disabled_account_is_not_authorized(self) -> None:
        self.add_user(is_active=False)
        response, _, _ = self.complete()
        self.assertIn("error=google_not_authorized", response.headers["location"])

    def test_wrong_workspace_domain_is_not_authorized(self) -> None:
        self.add_user()
        with patch("app.config.settings.google_allowed_domains", "school.org"):
            response, _, _ = self.complete({"hd": "gmail.com"})
        self.assertIn("error=google_not_authorized", response.headers["location"])

    def test_tampered_flow_cookie_is_rejected(self) -> None:
        self.client.cookies.set(
            google_sso.FLOW_COOKIE, "not-base64-json", path="/api/auth/google"
        )
        response = self.callback(code="c", state="s")
        self.assertIn("error=google_failed", response.headers["location"])


if __name__ == "__main__":
    unittest.main()
