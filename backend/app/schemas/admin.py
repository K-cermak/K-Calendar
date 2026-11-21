from datetime import datetime

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


class InstanceSettingsUpdate(BaseModel):
    registration_enabled: bool | None = None


class InstanceStatus(BaseModel):
    version: str
    user_count: int
    smtp_configured: bool
    oidc_configured: bool
    push_configured: bool
    password_login_enabled: bool
