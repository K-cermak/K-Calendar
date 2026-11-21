from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.deps import AppSettings, CurrentAuth
from app.db import DbSession
from app.schemas.account import (
    ApiTokenCreate,
    ApiTokenInfo,
    Clock,
    CreatedApiToken,
    Me,
    PasswordChange,
    ProfileUpdate,
    PushEndpoint,
    PushSubscriptionIn,
    RecoveryCodes,
    SessionInfo,
    TotpCode,
    TotpDisable,
    TotpSetup,
    TotpStatus,
)
from app.services import accounts, clock, zones
from app.services.auth import oidc, sessions, tokens, totp
from app.services.notify import devices

router = APIRouter(prefix="/me", tags=["account"])


@router.get("")
def get_me(auth: CurrentAuth) -> Me:
    return accounts.to_me(auth.user)


@router.get("/clock")
def get_clock(
    auth: CurrentAuth,
    tz: Annotated[str | None, Query(max_length=64, description="The profile's zone if left out")] = None,
) -> Clock:
    """What time it is for the user, so the app knows "today" without a time zone database."""
    zone = zones.check_zone(tz or auth.user.timezone)
    return Clock(timezone=zone, now=zones.format_local(zones.to_local(clock.now(), zone)))


@router.patch("")
def update_me(body: ProfileUpdate, auth: CurrentAuth, db: DbSession) -> Me:
    return accounts.to_me(accounts.update_profile(db, auth.user, body))


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, auth: CurrentAuth, db: DbSession) -> None:
    """Changes the password and signs out every other session."""
    accounts.change_password(
        db, auth.user, current=body.current_password, new=body.new_password, keep_session_id=auth.session.id
    )


@router.get("/sessions")
def list_sessions(auth: CurrentAuth, db: DbSession) -> list[SessionInfo]:
    return sessions.list_for(db, auth.user, auth.session.id)


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
def revoke_other_sessions(auth: CurrentAuth, db: DbSession) -> None:
    sessions.revoke_others(db, auth.user.id, auth.session.id)
    db.commit()


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(session_id: int, auth: CurrentAuth, db: DbSession) -> None:
    sessions.revoke(db, auth.user, session_id)


@router.post("/push-subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def subscribe_push(
    body: PushSubscriptionIn, request: Request, auth: CurrentAuth, db: DbSession, settings: AppSettings
) -> None:
    """Registers this browser for reminder notifications (the result of PushManager.subscribe)."""
    devices.subscribe(db, settings, auth.user, body, request.headers.get("user-agent"))


@router.post("/push-subscriptions/check")
def check_push(body: PushEndpoint, auth: CurrentAuth, db: DbSession) -> bool:
    """Whether this browser's subscription is registered for the signed-in user."""
    return devices.is_subscribed(db, auth.user, body.endpoint)


@router.post("/push-subscriptions/remove", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe_push(body: PushEndpoint, auth: CurrentAuth, db: DbSession) -> None:
    devices.unsubscribe(db, auth.user, body.endpoint)


@router.get("/totp")
def totp_status(auth: CurrentAuth, db: DbSession) -> TotpStatus:
    return TotpStatus(
        enabled=totp.is_enabled(auth.user), recovery_codes_left=totp.recovery_codes_left(db, auth.user)
    )


@router.post("/totp/setup")
def begin_totp(auth: CurrentAuth, db: DbSession, settings: AppSettings) -> TotpSetup:
    """Starts enrolment: a new secret for the authenticator app, active only once confirmed."""
    secret, uri = totp.begin_enrolment(db, settings, auth.user)
    return TotpSetup(secret=secret, uri=uri)


@router.post("/totp/enable")
def enable_totp(body: TotpCode, auth: CurrentAuth, db: DbSession, settings: AppSettings) -> RecoveryCodes:
    """Confirms enrolment with a code from the app. The recovery codes are shown only now."""
    return RecoveryCodes(codes=totp.confirm_enrolment(db, settings, auth.user, body.code))


@router.post("/totp/recovery-codes")
def renew_recovery_codes(
    body: TotpCode, auth: CurrentAuth, db: DbSession, settings: AppSettings
) -> RecoveryCodes:
    """Replaces all recovery codes; the old ones stop working."""
    return RecoveryCodes(codes=totp.new_recovery_codes(db, settings, auth.user, body.code))


@router.post("/totp/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_totp(body: TotpDisable, auth: CurrentAuth, db: DbSession, settings: AppSettings) -> None:
    totp.disable(db, settings, auth.user, password=body.password, code=body.code)


@router.get("/tokens")
def list_tokens(auth: CurrentAuth, db: DbSession) -> list[ApiTokenInfo]:
    return tokens.list_for(db, auth.user)


@router.post("/tokens", status_code=status.HTTP_201_CREATED)
def create_token(body: ApiTokenCreate, auth: CurrentAuth, db: DbSession) -> CreatedApiToken:
    """Creates an API token. The token itself is in this response only."""
    info, secret = tokens.create(db, auth.user, body)
    return CreatedApiToken(**info.model_dump(), token=secret)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: int, auth: CurrentAuth, db: DbSession) -> None:
    tokens.revoke(db, auth.user, token_id)


@router.delete("/oidc", status_code=status.HTTP_204_NO_CONTENT)
def unlink_oidc(auth: CurrentAuth, db: DbSession, settings: AppSettings) -> None:
    """Removes the single sign-on identity, unless it is the account's only way to sign in."""
    oidc.unlink(db, settings, auth.user)
