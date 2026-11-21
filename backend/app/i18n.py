"""Texts the server writes for people: e-mails, push notifications, default names (SPEC 8, 11).

A language is a JSON file in locales/ with the same keys as en.json; missing keys fall back to English.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).resolve().parent / "locales"


@cache
def _messages(locale: str) -> dict[str, Any]:
    path = LOCALES_DIR / f"{locale}.json"
    if not path.is_file() or not path.resolve().is_relative_to(LOCALES_DIR):
        return {}
    return json.loads(path.read_text())


def _lookup(messages: dict[str, Any], key: str) -> str | None:
    node: Any = messages
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]  # pyright: ignore[reportUnknownVariableType]
    return node if isinstance(node, str) else None


def t(locale: str, key: str, **values: object) -> str:
    text = _lookup(_messages(locale), key) or _lookup(_messages("en"), key) or key
    return text.format(**values) if values else text
