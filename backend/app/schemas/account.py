from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.admin import CAPTCHA_TOKEN_MAX

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


CaptchaToken = Field(default=None, max_length=CAPTCHA_TOKEN_MAX)


class RegisterRequest(SetupRequest):
    captcha_token: str | None = CaptchaToken


class LoginRequest(BaseModel):
    email: str = EMAIL
    password: str = PASSWORD
    captcha_token: str | None = CaptchaToken


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
    totp_enabled: bool
    oidc_linked: bool


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=64)
    locale: str | None = Field(default=None, pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    week_start: WeekStart | None = None
    time_format: TimeFormat | None = None
    default_view: DefaultView | None = None
    theme: Theme | None = None
    email_reminders_enabled: bool | None = None


class AccountDelete(BaseModel):
    """The password, or for an account without one, its e-mail address."""

    password: str | None = Field(default=None, max_length=1024)
    email: str | None = Field(default=None, max_length=320)


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
    captcha_token: str | None = CaptchaToken


class PasswordReset(TokenRequest):
    password: str = PASSWORD


class Clock(BaseModel):
    timezone: str
    now: str = Field(description="The current wall-clock time in the zone, without an offset")


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class PushSubscriptionIn(BaseModel):
    """What the browser's PushSubscription.toJSON() gives."""

    endpoint: str = Field(max_length=2000)
    keys: PushKeys


class PushEndpoint(BaseModel):
    endpoint: str = Field(max_length=2000)


class PasswordResetRequest(BaseModel):
    email: str = Field(max_length=320)


class TotpChallenge(BaseModel):
    """The password was right; a TOTP or recovery code is still needed to sign in."""

    totp_required: Literal[True] = True
    pending_token: str


class TotpLogin(BaseModel):
    pending_token: str = Field(max_length=200)
    code: str = Field(max_length=32)


class TotpSetup(BaseModel):
    secret: str
    uri: str


class TotpCode(BaseModel):
    code: str = Field(max_length=32)


class TotpDisable(TotpCode):
    password: str = PASSWORD


class TotpStatus(BaseModel):
    enabled: bool
    recovery_codes_left: int


class RecoveryCodes(BaseModel):
    codes: list[str]


TokenScope = Literal["read", "write"]


class ApiTokenCreate(BaseModel):
    name: str = Field(max_length=100)
    scope: TokenScope
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ApiTokenInfo(BaseModel):
    id: int
    name: str
    prefix: str
    scope: TokenScope
    created_at_utc: datetime
    last_used_at_utc: datetime | None
    expires_at_utc: datetime | None


class CreatedApiToken(ApiTokenInfo):
    """Includes the token itself, which is never shown again."""

    token: str
