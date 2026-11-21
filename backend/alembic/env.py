import os
from logging.config import fileConfig
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import Connection

import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport]  registers the models on Base.metadata
from alembic import context
from app.db import Base, make_engine
from app.models.types import UtcDateTime

config = context.config
target_metadata = Base.metadata


def _render_item(type_: str, obj: Any, _autogen_context: Any) -> str | Literal[False]:
    # Migrations must not import app code that may change later; the stored form is a plain DATETIME.
    if type_ == "type" and isinstance(obj, UtcDateTime):
        return "sa.DateTime()"
    return False


def _include_name(name: str | None, type_: str, _parent_names: Any) -> bool:
    # The search index is a virtual table made by hand in a migration, not a model.
    return not (type_ == "table" and name is not None and name.startswith("events_fts"))


def _migrate(connection: Connection) -> None:
    # Batch mode lets autogenerate express ALTER TABLE changes that SQLite does not support natively.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        render_item=_render_item,
        include_name=_include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    _migrate(connection)
else:
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)
    data_dir = Path(os.environ.get("APP_DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(data_dir / "app.db")
    with engine.begin() as conn:
        _migrate(conn)
