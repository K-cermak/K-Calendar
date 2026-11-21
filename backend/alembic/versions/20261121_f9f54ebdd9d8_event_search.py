"""event search

Revision ID: f9f54ebdd9d8
Revises: 46e2ac8c30e1
Create Date: 2026-11-21 07:54:38.282257
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f9f54ebdd9d8"
down_revision: str | None = "46e2ac8c30e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Full-text search over events (SPEC 9). unicode61 with remove_diacritics 2 folds case and
# diacritics for every script, so "zubar" finds "Zubař". The table keeps its own copy of the text;
# triggers keep it in step with events and their tags, including deletes that cascade from a
# calendar or a user, which the service layer never sees.
INDEX = """
    INSERT INTO events_fts (rowid, title, description, location, tags)
    SELECT e.id, e.title, e.description, e.location,
           coalesce((SELECT group_concat(t.name, ' ') FROM event_tags et
                     JOIN tags t ON t.id = et.tag_id WHERE et.event_id = e.id), '')
    FROM events e
"""
# {ids} is filled in below with fixed trigger expressions, never with input.
REFRESH = "DELETE FROM events_fts WHERE rowid IN ({ids}); " + INDEX + " WHERE e.id IN ({ids});"  # noqa: S608

TRIGGERS = {
    "events_fts_insert": ("AFTER INSERT ON events", REFRESH.format(ids="new.id")),
    "events_fts_update": (
        "AFTER UPDATE OF title, description, location ON events",
        REFRESH.format(ids="new.id"),
    ),
    "events_fts_delete": ("AFTER DELETE ON events", "DELETE FROM events_fts WHERE rowid = old.id;"),
    "events_fts_tag_added": ("AFTER INSERT ON event_tags", REFRESH.format(ids="new.event_id")),
    "events_fts_tag_removed": ("AFTER DELETE ON event_tags", REFRESH.format(ids="old.event_id")),
    "events_fts_tag_renamed": (
        "AFTER UPDATE OF name ON tags",
        REFRESH.format(ids="SELECT event_id FROM event_tags WHERE tag_id = new.id"),
    ),
}


def upgrade() -> None:
    op.execute(
        "CREATE VIRTUAL TABLE events_fts USING fts5("
        "title, description, location, tags, tokenize = 'unicode61 remove_diacritics 2')"
    )
    for name, (when, action) in TRIGGERS.items():
        op.execute(f"CREATE TRIGGER {name} {when} BEGIN {action} END")
    op.execute(INDEX)


def downgrade() -> None:
    for name in TRIGGERS:
        op.execute(f"DROP TRIGGER {name}")
    op.execute("DROP TABLE events_fts")
