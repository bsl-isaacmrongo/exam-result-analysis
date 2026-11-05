# Authentication

Authentication uses **server-side sessions stored in Postgres**. The browser
holds an opaque cookie, so there are no JWTs and no bearer tokens. Staff can
sign in with a **password** or with **Google**, and every account must be
created in advance by an admin through the CLI (there is no sign-up).

## Contents

1. [Accounts](#1-accounts)
2. [CSRF protection on every request](#2-csrf-protection-on-every-request)
3. [Password login](#3-password-login)
4. [Google sign-in](#4-google-sign-in)
5. [Sessions](#5-sessions)
6. [Protecting endpoints](#6-protecting-endpoints)
7. [Other endpoints](#7-other-endpoints)
8. [What's not finished yet](#whats-not-finished-yet)

## 1. Accounts

Accounts are rows in the `users` table ([`user.py`](../api/app/models/user.py)).
The fields that matter for login are:

| Field                   | Purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `email`                 | Login identifier, matched case-insensitively         |
| `role`                  | Used by `require_roles(...)`                         |
| `is_active`             | Disabled accounts cannot sign in or use sessions     |
| `password_hash`         | argon2id hash; `NULL` means Google sign-in only      |
| `google_sub`            | Google's stable account ID, linked on first sign-in  |
| `failed_login_attempts` | Counter for the lockout                              |
| `locked_until`          | Lockout expiry                                       |

Admins manage accounts with [`cli.py`](../api/app/cli.py):

```sh
python -m app.cli create-user jane@school.org --name "Jane Doe" --role admin --password
python -m app.cli set-password jane@school.org   # also revokes all sessions
python -m app.cli disable-user jane@school.org   # also revokes all sessions
python -m app.cli enable-user jane@school.org
python -m app.cli unlock-user jane@school.org
```

## 2. CSRF protection on every request

[`middleware.py`](../api/app/core/middleware.py) uses the **double-submit
cookie** pattern:

- Any response issues a readable `XSRF-TOKEN` cookie if the browser doesn't
  have one yet.
- Any non-GET request to `/api/*` must send the same value in an
  `X-XSRF-TOKEN` header. Otherwise it gets a **403** along with a fresh token.
- The login endpoint is **not** exempt. The UI therefore needs to make a GET
  first (normally `/api/auth/options`) before it can POST a login.

## 3. Password login

**`POST /api/auth/login`** with `{"email": "...", "password": "..."}`

1. [`PasswordLoginRequest`](../api/app/features/auth/schemas.py) only checks
   lengths. Password strength rules apply when a password is set, not at login.
2. [`authenticate_password`](../api/app/features/auth/service.py) does the
   checking:
   - It looks the user up by email, ignoring case.
   - It **always** runs an argon2id check, against a dummy hash if the user is
     unknown, disabled or has no password. This keeps response times the same
     whether or not the account exists.
   - If the account is unknown, disabled or has no password, it returns
     **401** `Invalid email or password`.
   - If the account is locked (`locked_until` is in the future), it returns
     **429**.
   - On a wrong password it increments `failed_login_attempts`. Once the count
     reaches `LOGIN_MAX_ATTEMPTS` (default 5), it locks the account for
     `LOGIN_LOCKOUT_MINUTES` (default 15), resets the counter, and returns
     **401**.
   - On success it resets the counter and lockout, re-hashes the password if
     argon2's parameters have changed, and returns the user.
3. `_start_session` in [`router.py`](../api/app/features/auth/router.py)
   creates the session ([section 5](#5-sessions)), sets the session cookie,
   rotates the CSRF token, and returns `{id, email, name, role}`.

## 4. Google sign-in

OpenID Connect **authorization code flow with PKCE**, implemented in
[`google_sso.py`](../api/app/features/auth/google_sso.py).

This only runs when `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and
`GOOGLE_REDIRECT_URI` are all set. `GET /api/auth/options` tells the UI
whether to show the Google button.

```text
Browser ──► GET /api/auth/google/login ──► 303 to Google (state, nonce, PKCE)
Google  ──► GET /api/auth/google/callback?code&state
API     ──► exchange code ─► verify ID token ─► find user ─► start session
API     ──► 303 to UI_BASE_URL + return path   (or /login?error=<code>)
```

### a. `GET /api/auth/google/login?return_url=...`

- The browser navigates here directly; this is not an XHR call.
- `begin` generates a random `state`, `nonce` and PKCE verifier, and cleans
  up the return path.
- The return path must be a local path. External URLs such as `//evil.com`
  and a return to `/login` both become `/`.
- These values go into the `bsl_google_flow` cookie: `HttpOnly`,
  `SameSite=Lax`, scoped to `/api/auth/google`, valid for 10 minutes.
- The handler then redirects (**303**) to Google with the PKCE challenge
  (`S256`), `prompt=select_account` and an `hd` hint if exactly one domain is
  allowed.

### b. `GET /api/auth/google/callback?code&state`

1. If Google returned `error=access_denied`, the result is `google_cancelled`.
   Any other Google error becomes `google_failed`.
2. `check_state` compares the cookie's `state` with the query's `state` in
   constant time. This prevents login CSRF.
3. `exchange_code` posts the code, client secret and PKCE verifier to Google's
   token endpoint and takes the `id_token` from the response.
4. `verify_google_id_token` ([`service.py`](../api/app/features/auth/service.py))
   checks:
   - the signature, issuer, expiry and audience (with 10 seconds of clock skew
     allowed);
   - that the `nonce` matches the one in the cookie;
   - that `email_verified` is true and `sub` and `email` are present;
   - if `GOOGLE_ALLOWED_DOMAINS` is set, that the `hd` claim is one of those
     domains.
5. `get_provisioned_user` finds the account:
   - It looks up `google_sub` first, then falls back to the email.
   - On the first Google sign-in it links the account by storing `google_sub`,
     and fills in `name` if empty.
   - If the email is already linked to a different `google_sub`, the account
     doesn't exist, or the user is disabled, the result is **403**, which maps
     to `google_not_authorized`.
6. On success the flow cookie is cleared (it is single-use), a session is
   started (`auth_method="google"`), and the browser is redirected (**303**) to
   `UI_BASE_URL` + return path.
7. On any failure the browser is redirected to
   `UI_BASE_URL/login?error=<code>&returnUrl=...`. The detailed reason is only
   written to the server log.

| Error code              | Meaning                                              |
| ----------------------- | ---------------------------------------------------- |
| `google_unavailable`    | SSO not configured, or Google could not be reached   |
| `google_cancelled`      | The user cancelled on Google's consent screen        |
| `google_failed`         | State, code exchange or token verification failed    |
| `google_not_authorized` | No matching active account, or domain not allowed    |

## 5. Sessions

[`sessions.py`](../api/app/core/sessions.py) handles session storage and
checks.

**Creating a session** (`create_session`):

- It first deletes this user's expired or revoked sessions.
- It generates a random 32-byte token, stores **only its SHA-256 hash** in
  `user_sessions` (with the IP address, user agent, auth method and
  `expires_at`), and updates `last_login_at`.

**The cookie:** `bsl_session` — `HttpOnly; Secure; SameSite=Strict; Path=/`,
with `max_age` equal to the absolute session lifetime.

**Checking a session** (`resolve_session`):

- It hashes the cookie token and looks up the row.
- The session is rejected if it:
  - was revoked;
  - is older than `SESSION_ABSOLUTE_MINUTES` (default 8 hours); or
  - has been idle longer than `SESSION_IDLE_MINUTES` (default 2 hours).
- Expired sessions are marked revoked when they are found.
- `last_seen_at` is only written at most once every 60 seconds.

## 6. Protecting endpoints

[`dependencies.py`](../api/app/core/dependencies.py) provides three FastAPI
dependencies:

| Dependency                 | Behaviour                                                                 |
| -------------------------- | ------------------------------------------------------------------------- |
| `get_current_session`      | **401** if there's no live session or the user is disabled. A disabled user is cut off on their next request. |
| `get_current_user`         | Returns the session's user.                                               |
| `require_roles("admin", ...)` | **403** if the user's role isn't in the list.                          |

Example:

```python
@router.get("/api/dashboard/summary")
def summary(user: User = Depends(require_roles("admin", "teacher"))):
    ...
```

## 7. Other endpoints

| Method | Path                         | Purpose                                                                 |
| ------ | ---------------------------- | ----------------------------------------------------------------------- |
| GET    | `/api/auth/options`          | Which sign-in methods are enabled                                       |
| POST   | `/api/auth/login`            | Password login; sets the session cookie                                 |
| GET    | `/api/auth/google/login`     | Browser navigation; redirects to Google                                 |
| GET    | `/api/auth/google/callback`  | Google redirect target; starts a session and redirects to the UI        |
| GET    | `/api/auth/me`               | Current user, or **401**. The UI uses this to check whether someone is signed in. |
| POST   | `/api/auth/logout`           | Needs the CSRF header. Safe to call repeatedly: revokes the session if one is live, clears the session cookie, and rotates the CSRF token. |

## What's not finished yet

- **Only `/api/auth/me` is protected right now.** `main.py` only mounts the
  auth router. The uploads router isn't mounted, and it imports
  `app.models.upload`, which doesn't exist. `require_roles` exists but nothing
  uses it yet, so the data endpoints will need these dependencies once they're
  added.
- **A 429 reveals that an account exists.** A locked account gets 429 while an
  unknown email gets 401.
- **Brute-force protection is per account only.** Nothing limits attempts by
  IP address, so one client can try many different emails without being
  slowed down.
- **The Google flow cookie isn't signed.** That's acceptable as built: it's
  `HttpOnly`, the `state` check ties it to this browser, and Google enforces
  the PKCE verifier.
- **First Google sign-in links by verified email.** Anyone who controls a
  pre-provisioned email address at Google can claim that account. Setting
  `GOOGLE_ALLOWED_DOMAINS` limits this to your Workspace domain.
