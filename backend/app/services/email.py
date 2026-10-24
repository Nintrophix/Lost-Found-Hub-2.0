"""Outgoing email. The console backend logs messages for local development only."""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from fastapi import BackgroundTasks

from app.core.config import Settings, get_settings

logger = logging.getLogger("app.email")


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, email: OutgoingEmail) -> None: ...


class ConsoleEmailSender:
    def send(self, email: OutgoingEmail) -> None:
        logger.warning("Development email to %s\nSubject: %s\n\n%s", email.to, email.subject, email.body)


class MemoryEmailSender:
    """Collects messages in a list. Used by tests."""

    def __init__(self) -> None:
        self.outbox: list[OutgoingEmail] = []

    def send(self, email: OutgoingEmail) -> None:
        self.outbox.append(email)


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, email: OutgoingEmail) -> None:
        s = self._settings
        message = EmailMessage()
        message["From"] = s.email_from
        message["To"] = email.to
        message["Subject"] = email.subject
        message.set_content(email.body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
            if s.smtp_use_tls:
                smtp.starttls()
            if s.smtp_username:
                smtp.login(s.smtp_username, s.smtp_password)
            smtp.send_message(message)


class BackgroundEmailSender:
    """Defers delivery until after the response is sent.

    Response time then no longer depends on whether an email went out (which would reveal whether an
    account exists), and nothing is sent if the request fails before its response.
    """

    def __init__(self, tasks: BackgroundTasks, inner: EmailSender) -> None:
        self._tasks = tasks
        self._inner = inner

    def send(self, email: OutgoingEmail) -> None:
        self._tasks.add_task(self._deliver, email)

    def _deliver(self, email: OutgoingEmail) -> None:
        try:
            self._inner.send(email)
        except Exception:
            logger.exception("Failed to deliver email with subject %r", email.subject)


def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.email_backend == "smtp":
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()
