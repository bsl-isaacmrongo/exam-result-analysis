# API database setup

The API uses PostgreSQL through SQLAlchemy. To start a local database with Docker
Compose:

1. Copy `.env.example` to `.env`.
2. Change `POSTGRES_PASSWORD` and use the same password in `DATABASE_URL`.
   URL-encode special characters in the URL password.
3. Start the database and install the API dependencies:

   ```sh
   docker compose up -d db
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```

4. From the `api` directory, start the API and check `http://127.0.0.1:8000/health/db`:

   ```sh
   uvicorn app.main:app --reload
   ```

The connection URL is loaded from `DATABASE_URL` in `.env`; credentials should
not be committed. The database health endpoint executes `SELECT 1` and reports
connection errors as request failures.

## Authentication

Staff sign in with **email + password** or **Google**. There is no public
registration: an administrator pre-provisions every account.

### Design

- **Server-side sessions.** On login the API sets `bsl_session`, a random
  opaque token in an `HttpOnly; Secure; SameSite=Strict` cookie. Only its
  SHA-256 hash is stored (`user_sessions`). Sessions expire after
  `SESSION_ABSOLUTE_MINUTES` (default 8h) or `SESSION_IDLE_MINUTES` of
  inactivity (default 2h), and logout / disabling a user revokes them
  immediately. No token is ever exposed to JavaScript.
- **CSRF.** Double-submit cookie: the API issues a readable `XSRF-TOKEN`
  cookie and requires a matching `X-XSRF-TOKEN` header on every non-GET
  `/api/*` request. The UI's `apiInterceptor` adds the header and
  `withCredentials` to API requests only. The token is rotated on login and
  logout.
- **Passwords** are hashed with argon2id. Login errors are generic and take the
  same time whether or not the account exists. After `LOGIN_MAX_ATTEMPTS`
  wrong passwords, the account is locked for `LOGIN_LOCKOUT_MINUTES`.
- **Google SSO** uses the OpenID Connect authorization-code flow with PKCE.
  `GET /api/auth/google/login` stores `state`, `nonce` and a PKCE verifier in a
  short-lived HttpOnly cookie and redirects to Google. Google redirects back to
  `GET /api/auth/google/callback`, where the API checks `state`, exchanges the
  code using the client secret and PKCE verifier, then verifies the ID token
  (signature, audience, issuer, expiry, nonce, `email_verified`, and optionally
  the Workspace domain via `GOOGLE_ALLOWED_DOMAINS`). Only pre-provisioned,
  active users get a session; the first Google sign-in links the account to
  Google's stable subject ID. The browser is then redirected back to the UI.
  Failures redirect to `UI_BASE_URL/login?error=<code>`, which shows a short
  message and never the raw error.

The UI calls the API directly at the URL in
`ui/src/environments/environment*.ts` (`apiBaseUrl`, default
`http://localhost:8000/`). The API only accepts credentialed cross-origin
requests from `CORS_ORIGINS` (default `http://localhost:4200`); add your
production UI origin there.

The UI's interceptor reads the `XSRF-TOKEN` cookie with `document.cookie`, so the
UI page must be able to see the API's cookies. That holds on `localhost`,
where cookies are shared across ports. In production, serve the UI and API from
the same host (e.g. `https://results.school.org` and
`https://results.school.org/api` behind one reverse proxy).

### Endpoints

| Method | Path                | Purpose                                         |
| ------ | ------------------- | ----------------------------------------------- |
| GET    | `/api/auth/options` | Which sign-in methods are enabled               |
| POST   | `/api/auth/login`   | `{"email", "password"}` → sets session cookie    |
| GET    | `/api/auth/google/login`    | Browser navigation: redirects to Google  |
| GET    | `/api/auth/google/callback` | Google redirect target: session → UI     |
| POST   | `/api/auth/logout`  | Revokes session, clears cookie (idempotent)      |
| GET    | `/api/auth/me`      | Current user, 401 if not signed in              |

### Google Cloud console

Use an OAuth client of type **Web application**. Under **Authorized redirect
URIs**, add the callback exactly as it appears in `GOOGLE_REDIRECT_URI`, e.g.
`http://localhost:8000/api/auth/google/callback`, plus the production
`https://.../api/auth/google/callback`. JavaScript origins are not needed.
Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` and
`UI_BASE_URL` in `.env`. Google SSO stays disabled (the login page falls back to
email + password) until all of them are set.

### Managing users

From the `api` directory, after `alembic upgrade head`:

```sh
python -m app.cli create-user jane@school.org --name "Jane Doe" --role admin --password
python -m app.cli create-user john@school.org          # Google sign-in only
python -m app.cli set-password jane@school.org         # also signs out all sessions
python -m app.cli unlock-user jane@school.org
python -m app.cli disable-user john@school.org         # also signs out all sessions
```

Passwords must be at least 12 characters.

### Tests

```sh
python -m unittest discover -s tests
```
