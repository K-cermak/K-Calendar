from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class AdminUser(BaseModel):
    id: int
    email: str
    display_name: str
    is_admin: bool
    is_active: bool
    has_password: bool
    totp_enabled: bool
    oidc_linked: bool
    created_at_utc: datetime
    last_seen_at_utc: datetime | None


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class InviteCreate(BaseModel):
    email: str | None = Field(default=None, max_length=320)


class CreatedLink(BaseModel):
    """A one-time link. The URL is only available in this response; the server keeps a hash."""

    id: int
    url: str
    expires_at_utc: datetime
    emailed: bool = False


class PendingInvite(BaseModel):
    id: int
    email: str | None
    created_at_utc: datetime
    expires_at_utc: datetime


class InstanceSettings(BaseModel):
    registration_enabled: bool
    session_days: int = Field(description="Days without use before a sign-in ends")


class InstanceSettingsUpdate(BaseModel):
    registration_enabled: bool | None = None
    session_days: Annotated[int, Field(ge=1, le=3650)] | None = None


CaptchaProvider = Literal["none", "recaptcha", "turnstile", "hcaptcha", "altcha"]
CaptchaPlacement = Literal["login", "registration", "both"]
# reCAPTCHA and hCaptcha tokens run to a few kilobytes.
CAPTCHA_TOKEN_MAX = 10_000


class CaptchaSettings(BaseModel):
    provider: CaptchaProvider
    placement: CaptchaPlacement
    site_key: str
    secret_key_set: bool = Field(description="The secret key itself is never sent back")


class CaptchaUpdate(BaseModel):
    provider: CaptchaProvider
    placement: CaptchaPlacement
    site_key: str = Field(default="", max_length=200)
    secret_key: str = Field(default="", max_length=200, description="Empty keeps the stored key")
    token: str | None = Field(
        default=None,
        max_length=CAPTCHA_TOKEN_MAX,
        description="Solved with the new keys; required when the provider or keys change",
    )


class InstanceStatus(BaseModel):
    version: str
    user_count: int
    smtp_configured: bool
    oidc_configured: bool
    push_configured: bool
    password_login_enabled: bool
