from fastapi import APIRouter, status

from app.api.deps import CurrentApiAuth
from app.db import DbSession
from app.schemas.calendar import TagCreate, TagOut, TagUpdate
from app.services import tags

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
def list_tags(auth: CurrentApiAuth, db: DbSession) -> list[TagOut]:
    return tags.list_for(db, auth.user)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_tag(body: TagCreate, auth: CurrentApiAuth, db: DbSession) -> TagOut:
    return tags.create(db, auth.user, body)


@router.patch("/{tag_id}")
def update_tag(tag_id: int, body: TagUpdate, auth: CurrentApiAuth, db: DbSession) -> TagOut:
    return tags.update(db, auth.user, tag_id, body)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, auth: CurrentApiAuth, db: DbSession) -> None:
    """Removes the tag from its events; the events stay."""
    tags.delete(db, auth.user, tag_id)
