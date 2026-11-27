from fastapi import APIRouter, Request, status

from app.api.deps import AdminAuth, AppSettings, Captcha, client_ip
from app.db import DbSession
from app.errors import AppError
from app.schemas.admin import (
    AdminUser,
    AdminUserUpdate,
    CaptchaSettings,
    CaptchaUpdate,
    CreatedLink,
    InstanceSettings,
    InstanceSettingsUpdate,
    InstanceStatus,
    InviteCreate,
    PendingInvite,
)
from app.services import admin, captcha, instance, invites
from app.services.notify import email
from app.services.reminders import DeliveryError

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(_auth: AdminAuth, db: DbSession) -> list[AdminUser]:
    return admin.list_users(db)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: AdminUserUpdate, auth: AdminAuth, db: DbSession) -> AdminUser:
    return admin.update_user(db, auth.user, user_id, body)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, auth: AdminAuth, db: DbSession) -> None:
    admin.delete_user(db, auth.user, user_id)


@router.delete("/users/{user_id}/totp", status_code=status.HTTP_204_NO_CONTENT)
def reset_totp(user_id: int, _auth: AdminAuth, db: DbSession) -> None:
    """Turns off two-step verification for a user who lost the authenticator and the codes."""
    admin.reset_totp(db, user_id)


@router.post("/users/{user_id}/reset-link", status_code=status.HTTP_201_CREATED)
def create_reset_link(user_id: int, auth: AdminAuth, db: DbSession, settings: AppSettings) -> CreatedLink:
    return invites.create_reset_link(db, settings, auth.user, user_id)


@router.get("/invites")
def list_invites(_auth: AdminAuth, db: DbSession) -> list[PendingInvite]:
    return invites.list_pending(db)


@router.post("/invites", status_code=status.HTTP_201_CREATED)
def create_invite(body: InviteCreate, auth: AdminAuth, db: DbSession, settings: AppSettings) -> CreatedLink:
    return invites.create_invite(db, settings, auth.user, body.email)


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(invite_id: int, _auth: AdminAuth, db: DbSession) -> None:
    invites.revoke_invite(db, invite_id)


@router.get("/settings")
def get_settings(_auth: AdminAuth, db: DbSession) -> InstanceSettings:
    return instance.get_settings(db)


@router.patch("/settings")
def update_settings(body: InstanceSettingsUpdate, _auth: AdminAuth, db: DbSession) -> InstanceSettings:
    return instance.update_settings(db, body)


@router.get("/status")
def get_status(_auth: AdminAuth, db: DbSession, settings: AppSettings) -> InstanceStatus:
    return instance.status(settings, db)


@router.get("/captcha")
def get_captcha(_auth: AdminAuth, db: DbSession) -> CaptchaSettings:
    return captcha.admin_view(db)


@router.put("/captcha")
def update_captcha(
    body: CaptchaUpdate, request: Request, _auth: AdminAuth, db: DbSession, verifier: Captcha
) -> CaptchaSettings:
    """New keys need a token solved with them, so a mistake cannot lock everyone out."""
    return captcha.update(db, verifier, body, client_ip(request))


@router.post("/test-email", status_code=status.HTTP_204_NO_CONTENT)
def send_test_email(auth: AdminAuth, settings: AppSettings) -> None:
    """Sends a test message to the admin's own address, to check the SMTP settings."""
    if not settings.smtp_enabled:
        raise AppError(409, "email_disabled", "E-mail is not configured")
    try:
        email.send_test(settings, auth.user.locale, auth.user.email)
    except DeliveryError as exc:
        raise AppError(502, "email_failed", str(exc)) from None
