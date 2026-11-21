from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Theme = Literal["system", "light", "dark"]
# "auto" is week on a wide screen and agenda on a phone (SPEC 11).
DefaultView = Literal["auto", "month", "week", "day", "agenda"]
WeekStart = Literal["monday", "sunday"]
TimeFormat = Literal["12", "24"]

EMAIL = Field(max_length=320)
PASSWORD = Field(max_length=1024)
DISPLAY_NAME = Field(max_length=100)
TIMEZONE = Field(max_length=64, description="IANA time zone name, such as Europe/Prague")


class SetupRequest(BaseModel):
    email: str = EMAIL
    display_name: str = DISPLAY_NAME
    password: str = PASSWORD
    timezone: str | None = Field(default=None, max_length=64, description="The browser's zone, if known")


class RegisterRequest(SetupRequest):
    pass


class LoginRequest(BaseModel):
    email: str = EMAIL
    password: str = PASSWORD


class Me(BaseModel):
    id: int
    email: str
    display_name: str
    is_admin: bool
    timezone: str
    locale: str
    week_start: WeekStart
    time_format: TimeFormat
    default_view: DefaultView
    theme: Theme
    email_reminders_enabled: bool
    has_password: bool


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=64)
    locale: str | None = Field(default=None, pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    week_start: WeekStart | None = None
    time_format: TimeFormat | None = None
    default_view: DefaultView | None = None
    theme: Theme | None = None


class PasswordChange(BaseModel):
    current_password: str = PASSWORD
    new_password: str = PASSWORD


class SessionInfo(BaseModel):
    id: int
    auth_method: str
    created_at_utc: datetime
    last_seen_at_utc: datetime
    expires_at_utc: datetime
    user_agent: str | None
    ip: str | None
    current: bool


class TokenRequest(BaseModel):
    token: str = Field(max_length=200)


class LinkInfo(BaseModel):
    email: str | None


class InviteAccept(TokenRequest):
    email: str | None = Field(default=None, max_length=320)
    display_name: str = DISPLAY_NAME
    password: str = PASSWORD
    timezone: str | None = Field(default=None, max_length=64)


class PasswordReset(TokenRequest):
    password: str = PASSWORD
