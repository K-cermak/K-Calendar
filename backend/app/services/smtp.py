"""The mail server, set by an admin in the administration rather than the environment (SPEC 8).

The settings live in the `settings` table as JSON. The password is encrypted there with a key
derived from the secret key, like the TOTP secrets, and never leaves the server again.
"""

import base64
import json
import logging
import re
from dataclasses import asdict, dataclass, replace
from typing import cast

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import InvalidInputError
from app.models import Setting
from app.schemas.admin import SmtpSecurity, SmtpSettings, SmtpUpdate
from app.services.auth import credentials

logger = logging.getLogger(__name__)

_KEY = "smtp"
DEFAULT_PORTS: dict[SmtpSecurity, int] = {"starttls": 587, "ssl": 465, "none": 25}
_ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+$")


@dataclass(frozen=True)
class SmtpConfig:
    host: str = ""
    port: int | None = None
    username: str = ""
    password: str = ""
    from_address: str = ""
    security: SmtpSecurity = "starttls"

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.from_address)

    @property
    def resolved_port(self) -> int:
        return self.port or DEFAULT_PORTS[self.security]


def _fernet(settings: Settings) -> Fernet:
    key = credentials.derive_key(settings.resolved_secret_key, "smtp-password")
    return Fernet(base64.urlsafe_b64encode(key))


def _stored(db: Session) -> dict[str, object]:
    row = db.get(Setting, _KEY)
    return cast(dict[str, object], json.loads(row.value)) if row is not None else {}


def load(db: Session, settings: Settings) -> SmtpConfig:
    """The settings with the password readable, for sending."""
    stored = _stored(db)
    encrypted = cast(str, stored.pop("password_encrypted", ""))
    password = ""
    if encrypted:
        try:
            password = _fernet(settings).decrypt(encrypted.encode()).decode()
        except InvalidToken:
            # The secret key changed since the password was saved; the admin has to enter it again.
            logger.warning("The SMTP password cannot be read; enter it again in the administration")
    return SmtpConfig(
        host=cast(str, stored.get("host", "")),
        port=cast(int | None, stored.get("port")),
        username=cast(str, stored.get("username", "")),
        password=password,
        from_address=cast(str, stored.get("from_address", "")),
        security=cast(SmtpSecurity, stored.get("security", "starttls")),
    )


def enabled(db: Session) -> bool:
    stored = _stored(db)
    return bool(stored.get("host") and stored.get("from_address"))


def sender(db: Session) -> str:
    """The From address, or empty while e-mail is off."""
    stored = _stored(db)
    return cast(str, stored.get("from_address", "")) if stored.get("host") else ""


def _save(db: Session, settings: Settings, config: SmtpConfig) -> None:
    data = asdict(config)
    password = data.pop("password")
    data["password_encrypted"] = _fernet(settings).encrypt(password.encode()).decode() if password else ""
    db.merge(Setting(key=_KEY, value=json.dumps(data)))


def admin_view(db: Session) -> SmtpSettings:
    stored = _stored(db)
    return SmtpSettings(
        host=cast(str, stored.get("host", "")),
        port=cast(int | None, stored.get("port")),
        username=cast(str, stored.get("username", "")),
        from_address=cast(str, stored.get("from_address", "")),
        security=cast(SmtpSecurity, stored.get("security", "starttls")),
        password_set=bool(stored.get("password_encrypted")),
    )


def update(db: Session, settings: Settings, change: SmtpUpdate) -> SmtpSettings:
    """Saves the settings. An empty password keeps the stored one, unless the user name is cleared."""
    host = change.host.strip()
    from_address = change.from_address.strip()
    if bool(host) != bool(from_address):
        raise InvalidInputError(
            "smtp_incomplete", "Fill in both the server and the sender address, or neither"
        )
    if any(c.isspace() for c in host):
        raise InvalidInputError("smtp_host_invalid", "Enter the mail server's name without spaces")
    if from_address and not _ADDRESS.match(from_address):
        raise InvalidInputError("invalid_email", "Enter a valid e-mail address")
    username = change.username.strip()
    current = load(db, settings)
    password = change.password or (current.password if username else "")
    config = replace(
        current,
        host=host,
        port=change.port,
        username=username,
        password=password if username else "",
        from_address=from_address,
        security=change.security,
    )
    _save(db, settings, config)
    db.commit()
    return admin_view(db)
