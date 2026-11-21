from collections import Counter

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.models import Tag, User
from app.palette import PALETTE
from app.schemas.calendar import TagCreate, TagOut, TagUpdate


def to_out(tag: Tag) -> TagOut:
    return TagOut.model_validate({"id": tag.id, "name": tag.name, "color": tag.color})


def _key(name: str) -> str:
    return name.casefold()


def _check_name(name: str) -> str:
    # Inner runs of whitespace collapse, so "kids" and "kids " are the same tag.
    cleaned = " ".join(name.split())
    if not cleaned:
        raise InvalidInputError("name_required", "Enter a name")
    return cleaned


def list_for(db: Session, user: User) -> list[TagOut]:
    rows = db.scalars(select(Tag).where(Tag.user_id == user.id).order_by(Tag.name_key))
    return [to_out(tag) for tag in rows]


def get_owned(db: Session, user: User, tag_id: int) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None or tag.user_id != user.id:
        raise NotFoundError()
    return tag


def least_used_color(db: Session, user: User) -> str:
    """The palette colour fewest of the user's tags have, so the first tags come out distinct."""
    used = Counter(db.scalars(select(Tag.color).where(Tag.user_id == user.id)))
    return min(PALETTE, key=lambda color: (used[color], PALETTE.index(color)))


def _find(db: Session, user: User, name: str) -> Tag | None:
    return db.scalar(select(Tag).where(Tag.user_id == user.id, Tag.name_key == _key(name)))


def _new(db: Session, user: User, name: str, color: str | None) -> Tag:
    tag = Tag(user_id=user.id, name=name, name_key=_key(name), color=color or least_used_color(db, user))
    db.add(tag)
    db.flush()
    return tag


def create(db: Session, user: User, body: TagCreate) -> TagOut:
    name = _check_name(body.name)
    if _find(db, user, name) is not None:
        raise ConflictError("tag_exists", "A tag with this name already exists")
    tag = _new(db, user, name, body.color)
    db.commit()
    return to_out(tag)


def resolve(db: Session, user: User, names: list[str]) -> list[Tag]:
    """The user's tags with these names, creating the ones that do not exist yet (SPEC 7)."""
    result: dict[str, Tag] = {}
    for raw in names:
        name = _check_name(raw)
        if _key(name) in result:
            continue
        result[_key(name)] = _find(db, user, name) or _new(db, user, name, None)
    return list(result.values())


def update(db: Session, user: User, tag_id: int, body: TagUpdate) -> TagOut:
    tag = get_owned(db, user, tag_id)
    if body.name is not None:
        name = _check_name(body.name)
        other = _find(db, user, name)
        if other is not None and other.id != tag.id:
            raise ConflictError("tag_exists", "A tag with this name already exists")
        tag.name, tag.name_key = name, _key(name)
    if body.color is not None:
        tag.color = body.color
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("tag_exists", "A tag with this name already exists") from None
    return to_out(tag)


def delete(db: Session, user: User, tag_id: int) -> None:
    """Removes the tag from its events; the events themselves stay."""
    db.delete(get_owned(db, user, tag_id))
    db.commit()
