"""SMTP sending with guardrails.

Sending email is the only irreversible thing this system does, so it is the
most defensive module in the project. Every send has to pass, in order:

* the global send switch (`SEND_ENABLED`, off by default),
* the daily cap and the per company cooling off window,
* the suppression list,
* a valid recipient address and both attachments existing on disk.

Dry run is the default everywhere. A message is only handed to SMTP when the
caller has explicitly asked for a live send.
"""

from __future__ import annotations

import mimetypes
import random
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Sequence

from ..models import utcnow
from ..util import env, log

_ADDRESS_OK = ("@", ".")


class SendBlocked(RuntimeError):
    """A guardrail refused the send. The caller should report, not retry."""


@dataclass(slots=True)
class SendResult:
    ok: bool
    recipient: str
    message_id: str = ""
    error: str = ""
    dry_run: bool = False
    sent_at: str = ""


class Mailer:
    def __init__(
        self,
        *,
        sender_email: str | None = None,
        password: str | None = None,
        sender_name: str = "",
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self.sender_email = sender_email or env.get("SENDER_EMAIL", "") or ""
        self.password = password or env.get("SMTP_PASSWORD") or env.get("GMAIL_APP_PASSWORD", "")
        self.sender_name = sender_name or env.get("SENDER_NAME", "") or ""
        self.host = host or env.get("SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com"
        self.port = port or env.get_int("SMTP_PORT", 465)
        self.reply_to = env.get("REPLY_TO_EMAIL", "") or ""

    # -------------------------------------------------------------- checks

    def ready(self) -> tuple[bool, str]:
        if not self.sender_email:
            return False, "SENDER_EMAIL is not set"
        if not self.password:
            return False, "SMTP_PASSWORD (or GMAIL_APP_PASSWORD) is not set"
        return True, ""

    @staticmethod
    def send_enabled() -> bool:
        """The master switch. Without it, every send is a dry run."""
        return env.get_bool("SEND_ENABLED", False)

    @staticmethod
    def valid_address(address: str) -> bool:
        return bool(address) and all(token in address for token in _ADDRESS_OK) and " " not in address

    # -------------------------------------------------------------- compose

    def build_message(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        attachments: Sequence[str | Path] = (),
        in_reply_to: str = "",
        references: str = "",
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = (
            formataddr((self.sender_name, self.sender_email))
            if self.sender_name
            else self.sender_email
        )
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain=self.sender_email.split("@")[-1])
        if self.reply_to:
            message["Reply-To"] = self.reply_to
        # Threading headers are what make a follow up land under the original
        # message rather than arriving as a second cold email.
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = (references or in_reply_to).strip()
        message.set_content(body)

        for path in attachments:
            file_path = Path(path)
            if not file_path.exists():
                raise SendBlocked(f"attachment missing: {file_path}")
            guessed, _ = mimetypes.guess_type(file_path.name)
            maintype, _, subtype = (guessed or "application/octet-stream").partition("/")
            message.add_attachment(
                file_path.read_bytes(),
                maintype=maintype,
                subtype=subtype or "octet-stream",
                filename=file_path.name,
            )
        return message

    # ----------------------------------------------------------------- send

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        attachments: Sequence[str | Path] = (),
        in_reply_to: str = "",
        references: str = "",
        dry_run: bool = True,
    ) -> SendResult:
        """Send one message. `dry_run=True` builds and validates without sending."""
        if not self.valid_address(to):
            return SendResult(ok=False, recipient=to, error="invalid recipient address")

        try:
            message = self.build_message(
                to=to,
                subject=subject,
                body=body,
                attachments=attachments,
                in_reply_to=in_reply_to,
                references=references,
            )
        except SendBlocked as exc:
            return SendResult(ok=False, recipient=to, error=str(exc))

        message_id = message["Message-ID"]

        if dry_run or not self.send_enabled():
            reason = "dry run" if dry_run else "SEND_ENABLED is not true"
            log.dim(f"[{reason}] would send '{subject}' to {to}")
            return SendResult(
                ok=True, recipient=to, message_id=message_id, dry_run=True, sent_at=""
            )

        ok, why = self.ready()
        if not ok:
            return SendResult(ok=False, recipient=to, error=why)

        context = ssl.create_default_context()
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=45) as smtp:
                    smtp.login(self.sender_email, self.password)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=45) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(self.sender_email, self.password)
                    smtp.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            return SendResult(
                ok=False,
                recipient=to,
                error=(
                    "SMTP authentication failed. For Gmail you need 2 step verification "
                    f"and a 16 character app password, not your account password. ({exc.smtp_code})"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return SendResult(ok=False, recipient=to, error=f"{type(exc).__name__}: {exc}")

        log.ok(f"sent '{subject}' to {to}")
        return SendResult(
            ok=True, recipient=to, message_id=message_id, dry_run=False, sent_at=utcnow()
        )

    @staticmethod
    def pace(index: int, total: int, minimum: int = 35, maximum: int = 75) -> None:
        """Human paced gaps between sends, so a batch does not look like a blast."""
        if index >= total - 1:
            return
        delay = random.randint(minimum, maximum)
        log.dim(f"waiting {delay}s before the next send")
        time.sleep(delay)
