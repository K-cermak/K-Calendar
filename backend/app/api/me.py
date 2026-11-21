from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentAuth
from app.db import DbSession
from app.schemas.account import Clock, Me, PasswordChange, ProfileUpdate, SessionInfo
from app.services import accounts, clock, zones
from app.services.auth import sessions

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
