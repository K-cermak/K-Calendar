"""Every error code the API can send has a message in the interface's language file."""

import json
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
FRONTEND_MESSAGES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales" / "en.json"

# The first argument of an error class, or a code= keyword.
CODE = re.compile(r'(?:[A-Z]\w*Error\(\s*|code=)"([a-z_]+)"')


def test_every_error_code_has_a_message() -> None:
    codes = {code for path in APP.rglob("*.py") for code in CODE.findall(path.read_text())}
    assert len(codes) > 30
    messages = json.loads(FRONTEND_MESSAGES.read_text())["errors"]
    assert sorted(codes - messages.keys()) == []
