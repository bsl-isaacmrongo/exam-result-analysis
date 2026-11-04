from pydantic import BaseModel, ConfigDict, Field

from app.core.security import PASSWORD_MAX_LENGTH


class PasswordLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    # No strength rules here: validation happens at password-set time, and
    # failing early on login would leak policy info for no benefit.
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class AuthOptionsResponse(BaseModel):
    password_enabled: bool = True
    google_enabled: bool


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None
    role: str
