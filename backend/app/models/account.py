from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import UtcDateTime


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("oidc_issuer", "oidc_subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str | None]
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    locale: Mapped[str] = mapped_column(String(16), default="en")
    week_start: Mapped[str] = mapped_column(String(8), default="monday")
    time_format: Mapped[str] = mapped_column(String(2), default="24")
    default_view: Mapped[str] = mapped_column(String(8), default="auto")
    theme: Mapped[str] = mapped_column(String(8), default="system")
    email_reminders_enabled: Mapped[bool] = mapped_column(default=False)
    totp_secret_encrypted: Mapped[str | None]
    totp_enabled_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime)
    totp_last_step: Mapped[int | None]
    oidc_issuer: Mapped[str | None] = mapped_column(String(500))
    oidc_subject: Mapped[str | None] = mapped_column(String(255))
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    auth_method: Mapped[str] = mapped_column(String(16))
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    last_seen_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at_utc: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip: Mapped[str | None] = mapped_column(String(64))


class Invite(Base):
    """An invite link, or with purpose "reset" a password reset link for user_id."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(8))
    email: Mapped[str | None] = mapped_column(String(320))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    used_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str]


class RecoveryCode(Base):
    """One-time TOTP recovery codes, stored as hashes (SPEC 6)."""

    __tablename__ = "recovery_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime)


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_prefix: Mapped[str] = mapped_column(String(16))
    scope: Mapped[str] = mapped_column(String(8))
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_used_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime)
    revoked_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime)
