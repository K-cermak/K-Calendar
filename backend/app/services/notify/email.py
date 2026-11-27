"""E-mail through the standard library's smtplib (SPEC 8): reminders, invites, password reset.

Every message has a plain-text part and an HTML part in the look of the app. The HTML is built from
tables with inline styles, which is what mail clients render reliably, and it loads nothing from
the network: the logo travels inside the message. Until an admin sets up the mail server in the
administration none of it is offered.
"""

import html
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from functools import cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.branding import get_branding
from app.config import Settings
from app.i18n import t
from app.services import smtp
from app.services.notify import messages
from app.services.reminders import Delivery, DeliveryError

TIMEOUT_S = 20
LOGO = Path(__file__).resolve().parents[2] / "assets" / "email-logo.png"

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
# The light colours are inline, as every client needs; clients that follow the system's dark mode
# (Apple Mail, Outlook for Mac) take the dark ones from here. The values are the app's tokens.
DARK = (
    "@media (prefers-color-scheme: dark){"
    ".bg{background:#0a0a0a!important}"
    ".card{background:#0a0a0a!important;border-color:#2e2e2e!important}"
    ".ink{color:#ededed!important}"
    ".muted{color:#a1a1a1!important}"
    ".line{border-color:#2e2e2e!important}}"
)


@dataclass
class Mail:
    """One message, before it is laid out as text and as HTML."""

    subject: str
    eyebrow: str
    title: str
    preheader: str
    rows: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    paragraphs: list[str] = field(default_factory=list[str])
    link: str | None = None
    button: str | None = None
    footer: list[str] = field(default_factory=list[str])


@cache
def _logo() -> bytes:
    return LOGO.read_bytes()


def _text(mail: Mail) -> str:
    parts = [mail.title]
    if mail.rows:
        parts.append("\n".join(f"{label}: {value}" for label, value in mail.rows))
    parts.extend(mail.paragraphs)
    if mail.link and mail.button:
        parts.append(f"{mail.button}: {mail.link}")
    if mail.footer:
        parts.append("\n".join(mail.footer))
    return "\n\n".join(parts) + "\n"


def _html(mail: Mail, locale: str, logo_cid: str) -> str:
    app = html.escape(get_branding().name)
    e = html.escape
    rows = "".join(
        f'<tr><td class="muted" style="padding:0 16px 6px 0;vertical-align:top;white-space:nowrap;'
        f'font:400 13px/1.6 {FONT};color:#666666">{e(label)}</td>'
        f'<td class="ink" style="padding:0 0 6px;font:400 15px/1.5 {FONT};color:#171717">{e(value)}</td></tr>'
        for label, value in mail.rows
    )
    body = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px">{rows}</table>'
        if rows
        else ""
    )
    # The last paragraph of a message without a button ends the card, so it keeps no space below.
    last = len(mail.paragraphs) - 1
    body += "".join(
        f'<p class="ink" style="margin:0 0 {0 if i == last and not mail.button else 24}px;'
        f'font:400 15px/1.6 {FONT};color:#171717">{e(p).replace(chr(10), "<br>")}</p>'
        for i, p in enumerate(mail.paragraphs)
    )
    if mail.link and mail.button:
        link = e(mail.link, quote=True)
        body += (
            f'<a href="{link}" style="display:inline-block;padding:11px 20px;background:#1f6fd6;'
            f'color:#ffffff;font:500 14px/1 {FONT};text-decoration:none">{e(mail.button)}</a>'
            f'<div class="line" style="margin:28px 0 0;padding:16px 0 0;border-top:1px solid #eaeaea;'
            f'font:400 12px/1.6 {FONT};color:#8f8f8f"><span class="muted" style="color:#8f8f8f">'
            f'{e(t(locale, "email.fallback"))}</span><br><a href="{link}" style="color:#666666;'
            f'font-family:{MONO};word-break:break-all">{e(mail.link)}</a></div>'
        )
    footer = "<br>".join(e(line) for line in mail.footer)
    return (
        f'<!doctype html><html lang="{e(locale)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f"<title>{e(mail.subject)}</title><style>{DARK}</style></head>"
        '<body class="bg" style="margin:0;padding:0;background:#fafafa">'
        # What the inbox shows after the subject, instead of the first words of the page.
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0">{e(mail.preheader)}</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="bg" '
        'style="background:#fafafa"><tr><td align="center" style="padding:40px 16px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px">'
        f'<tr><td style="padding:0 0 16px"><img src="cid:{logo_cid}" width="24" height="24" alt="" '
        'style="display:inline-block;vertical-align:middle;border:0;margin:0 8px 0 0">'
        f'<span class="ink" style="vertical-align:middle;font:600 15px/1 {FONT};letter-spacing:-0.01em;'
        f'color:#171717">{app}</span></td></tr>'
        '<tr><td class="card" style="background:#ffffff;border:1px solid #eaeaea;padding:32px">'
        f'<div class="muted" style="margin:0 0 8px;font:500 13px/1.4 {FONT};color:#666666">'
        f"{e(mail.eyebrow)}</div>"
        f'<h1 class="ink" style="margin:0 0 20px;font:600 22px/1.3 {FONT};letter-spacing:-0.02em;'
        f'color:#171717">{e(mail.title)}</h1>{body}</td></tr>'
        f'<tr><td class="muted" style="padding:16px 2px 0;font:400 12px/1.6 {FONT};color:#8f8f8f">'
        f"{footer}</td></tr>"
        "</table></td></tr></table></body></html>"
    )


def send(db: Session, settings: Settings, to: str, mail: Mail, locale: str) -> None:
    """Sends one message. Raises DeliveryError for anything the SMTP server or network refuses."""
    config = smtp.load(db, settings)
    if not config.enabled:
        raise DeliveryError("E-mail is not configured")
    domain = config.from_address.rpartition("@")[2] or None
    message = EmailMessage()
    message["From"] = config.from_address
    message["To"] = to
    message["Subject"] = mail.subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=domain)
    message.set_content(_text(mail))
    logo_cid = make_msgid("logo", domain=domain)
    message.add_alternative(_html(mail, locale, logo_cid[1:-1]), subtype="html")
    # The logo goes with the HTML as a related part, so clients show it without fetching anything.
    html_part = message.get_body(preferencelist=("html",))
    assert html_part is not None
    html_part.add_related(_logo(), "image", "png", cid=logo_cid, filename="logo.png")
    try:
        if config.security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                config.host, config.resolved_port, timeout=TIMEOUT_S, context=ssl.create_default_context()
            )
        else:
            server = smtplib.SMTP(config.host, config.resolved_port, timeout=TIMEOUT_S)
        with server:
            if config.security == "starttls":
                server.starttls(context=ssl.create_default_context())
            if config.username:
                server.login(config.username, config.password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise DeliveryError(f"The e-mail could not be sent: {exc}") from None


def _signature(locale: str, settings: Settings) -> str:
    return t(locale, "email.signature", app=get_branding().name, base_url=settings.base_url)


def send_reminder(db: Session, settings: Settings, delivery: Delivery) -> None:
    user, event = delivery.user, delivery.shown
    locale, app = user.locale, get_branding().name
    title = messages.title(user, event)
    rows = [(t(locale, "email.reminder.when"), messages.when(user, event, delivery.start))]
    if event.location:
        rows.append((t(locale, "email.reminder.where"), event.location))
    mail = Mail(
        subject=t(locale, "email.reminder.subject", title=title),
        eyebrow=t(locale, "email.reminder.eyebrow"),
        title=title,
        preheader=messages.reminder_body(user, event, delivery.start),
        rows=rows,
        link=f"{settings.base_url}/event/{delivery.occurrence_id}",
        button=t(locale, "email.reminder.button", app=app),
        footer=[t(locale, "email.reminder.settings"), _signature(locale, settings)],
    )
    send(db, settings, user.email, mail, locale)


def send_link(db: Session, settings: Settings, locale: str, to: str, kind: str, link: str) -> None:
    """An invite or a password reset link."""
    app = get_branding().name
    intro = t(locale, f"email.{kind}.text", app=app)
    mail = Mail(
        subject=t(locale, f"email.{kind}.subject", app=app),
        eyebrow=t(locale, f"email.{kind}.eyebrow"),
        title=t(locale, f"email.{kind}.title", app=app),
        preheader=intro,
        paragraphs=[intro],
        link=link,
        button=t(locale, f"email.{kind}.button"),
        footer=[_signature(locale, settings)],
    )
    send(db, settings, to, mail, locale)


def send_test(db: Session, settings: Settings, locale: str, to: str) -> None:
    app = get_branding().name
    text = t(locale, "email.test.text", app=app)
    mail = Mail(
        subject=t(locale, "email.test.subject", app=app),
        eyebrow=t(locale, "email.test.eyebrow"),
        title=t(locale, "email.test.title"),
        preheader=text,
        paragraphs=[text],
        footer=[_signature(locale, settings)],
    )
    send(db, settings, to, mail, locale)
