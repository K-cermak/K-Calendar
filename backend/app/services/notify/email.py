"""E-mail through the standard library's smtplib (SPEC 8): reminders, invites, password reset.

Every message has a plain-text and a simple HTML part. Without SMTP settings none of it is offered.
"""

import html
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from sqlalchemy.orm import Session

from app.branding import get_branding
from app.config import Settings
from app.i18n import t
from app.services.notify import messages
from app.services.reminders import Delivery, DeliveryError

TIMEOUT_S = 20


def send(settings: Settings, to: str, subject: str, text: str, html_body: str) -> None:
    """Sends one message. Raises DeliveryError for anything the SMTP server or network refuses."""
    if not settings.smtp_enabled or settings.smtp_host is None or settings.smtp_from is None:
        raise DeliveryError("E-mail is not configured")
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=settings.smtp_from.rpartition("@")[2] or None)
    message.set_content(text)
    message.add_alternative(html_body, subtype="html")
    port = settings.smtp_port or (
        465 if settings.smtp_security == "ssl" else 587 if settings.smtp_security == "starttls" else 25
    )
    try:
        if settings.smtp_security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host, port, timeout=TIMEOUT_S, context=ssl.create_default_context()
            )
        else:
            server = smtplib.SMTP(settings.smtp_host, port, timeout=TIMEOUT_S)
        with server:
            if settings.smtp_security == "starttls":
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password or "")
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise DeliveryError(f"The e-mail could not be sent: {exc}") from None


def _html(paragraphs: list[str], link: str | None = None, button: str | None = None) -> str:
    """A plain HTML version: the texts escaped, the link as a button. No remote images or styles."""
    body = "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)
    if link and button:
        body += (
            f'<p><a href="{html.escape(link, quote=True)}" style="display:inline-block;padding:10px 16px;'
            f'background:#1f6fd6;color:#ffffff;text-decoration:none">{html.escape(button)}</a></p>'
            f'<p style="color:#666666;font-size:12px">{html.escape(link)}</p>'
        )
    return (
        '<!doctype html><html><body style="font-family:system-ui,sans-serif;font-size:14px;'
        f'color:#171717;line-height:1.5">{body}</body></html>'
    )


def _signature(locale: str, settings: Settings) -> str:
    return t(locale, "email.signature", app=get_branding().name, base_url=settings.base_url)


def send_reminder(_db: Session, settings: Settings, delivery: Delivery) -> None:
    user, event = delivery.user, delivery.shown
    app = get_branding().name
    title = messages.title(user, event)
    when = messages.when(user, event, delivery.start)
    link = f"{settings.base_url}/event/{delivery.occurrence_id}"
    lines = [t(user.locale, "email.reminder.text", title=title, when=when)]
    if event.location:
        lines.append(t(user.locale, "email.reminder.location", location=event.location))
    footer = [t(user.locale, "email.reminder.settings"), _signature(user.locale, settings)]
    text = (
        "\n".join(lines)
        + "\n\n"
        + t(user.locale, "email.reminder.open", app=app, link=link)
        + "\n\n"
        + "\n".join(footer)
    )
    send(
        settings,
        user.email,
        t(user.locale, "email.reminder.subject", title=title),
        text,
        _html([*lines], link, app) + "",
    )


def send_link(settings: Settings, locale: str, to: str, kind: str, link: str) -> None:
    """An invite or a password reset link."""
    app = get_branding().name
    intro = t(locale, f"email.{kind}.text", app=app)
    button = t(locale, f"email.{kind}.button")
    signature = _signature(locale, settings)
    send(
        settings,
        to,
        t(locale, f"email.{kind}.subject", app=app),
        f"{intro}\n\n{link}\n\n{signature}",
        _html([intro], link, button) + "",
    )


def send_test(settings: Settings, locale: str, to: str) -> None:
    app = get_branding().name
    text = t(locale, "email.test.text", app=app)
    send(settings, to, t(locale, "email.test.subject", app=app), text, _html([text]))
