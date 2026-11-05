from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    # Optional overrides for the host/port in DATABASE_URL, e.g. DATABASE_HOST=db
    # inside Docker Compose, so the same .env works on the host and in containers.
    database_host: str | None = None
    database_port: int | None = None

    # Browser origins allowed to call the API with credentials (the UI).
    # Comma-separated, exact scheme://host:port, no trailing slash.
    cors_origins: str = "http://localhost:4200"

    # Where the API sends the browser after login/logout flows that leave the
    # SPA (Google SSO). No trailing slash.
    ui_base_url: str = "http://localhost:4200"

    # Google SSO (OpenID Connect authorization-code flow with PKCE).
    # Create an OAuth "Web application" client and register
    # GOOGLE_REDIRECT_URI under "Authorized redirect URIs".
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str | None = None
    # Optional comma-separated list of Google Workspace domains (the "hd"
    # claim) allowed to sign in, e.g. "braeburn.ac.ke". Empty = any domain,
    # but the account must still be pre-provisioned.
    google_allowed_domains: str = ""

    # Sessions
    session_absolute_minutes: int = Field(default=480, gt=0)
    session_idle_minutes: int = Field(default=120, gt=0)
    # Must stay True outside local development over plain HTTP.
    cookie_secure: bool = True

    # Password brute-force protection (per account)
    login_max_attempts: int = Field(default=5, gt=0)
    login_lockout_minutes: int = Field(default=15, gt=0)

    @model_validator(mode="after")
    def _apply_database_overrides(self) -> "Settings":
        overrides = {
            key: value
            for key, value in (
                ("host", self.database_host),
                ("port", self.database_port),
            )
            if value
        }
        if overrides:
            url = make_url(self.database_url).set(**overrides)
            self.database_url = url.render_as_string(hide_password=False)
        return self

    @property
    def google_sso_enabled(self) -> bool:
        return bool(
            self.google_client_id
            and self.google_client_secret
            and self.google_client_secret.get_secret_value()
            and self.google_redirect_uri
        )

    @property
    def ui_base(self) -> str:
        return self.ui_base_url.rstrip("/")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def google_allowed_domain_set(self) -> frozenset[str]:
        return frozenset(
            d.strip().casefold()
            for d in self.google_allowed_domains.split(",")
            if d.strip()
        )


settings = Settings()
