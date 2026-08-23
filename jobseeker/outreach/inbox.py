"""Reading replies over IMAP and turning them into pipeline state.

This closes the loop that the upstream project left open. Without it, the queue
only ever knows what was sent, never what came back, so follow ups keep firing
at people who already replied and the funnel numbers are fiction.

Classification is rule first, because the rules are cheap and cover most real
replies. Claude is consulted only for the genuinely ambiguous ones, and only if
a key is configured.
"""

from __future__ import annotations

import email
import imaplib
import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.utils import parseaddr
from typing import Any

from ..models import ApplicationStatus
from ..util import env, log
from ..util.text import normalize, truncate

REJECTION_MARKERS = (
    "unfortunately", "we regret", "not moving forward", "not proceeding",
    "decided not to", "will not be progressing", "unsuccessful",
    "we have decided to move forward with other", "no longer under consideration",
    "not a match at this time", "we won't be moving",
)
INTEREST_MARKERS = (
    "interview", "schedule a call", "book a time", "would love to chat",
    "let's set up", "are you available", "next steps", "speak with you",
    "phone screen", "technical screen", "meet the team", "calendly.com",
    "happy to chat", "we would like to",
)
OFFER_MARKERS = ("offer letter", "we are pleased to offer", "extend an offer", "offer of employment")
AUTO_MARKERS = (
    "out of office", "automatic reply", "auto-reply", "we have received your application",
    "thank you for applying", "your application has been received", "do not reply",
    "this mailbox is not monitored", "we will be in touch if",
)

# A bounce is not a reply. Treating it as one leaves a dead address looking
# like a live application and lets the follow up schedule chase it twice.
BOUNCE_SENDERS = ("mailer-daemon", "postmaster", "mail delivery subsystem", "no-reply@dmarc")
BOUNCE_MARKERS = (
    "address not found", "delivery status notification (failure)",
    "undelivered mail returned to sender", "delivery has failed",
    "recipient address rejected", "user unknown", "mailbox unavailable",
    "domain couldn't be found", "does not exist", "550 5.1.1", "550 5.4.1",
)

CLASSIFICATIONS = ("offer", "interested", "rejection", "auto_ack", "bounce", "other")


@dataclass(slots=True)
class IncomingMessage:
    uid: str
    from_addr: str
    from_name: str
    subject: str
    body: str
    in_reply_to: str
    references: str

    @property
    def snippet(self) -> str:
        return truncate(" ".join(self.body.split()), 400)


def classify_reply(subject: str, body: str, use_llm: bool = True, sender: str = "") -> str:
    """Return one of CLASSIFICATIONS for an incoming message."""
    haystack = normalize(f"{subject}\n{body[:4000]}")

    sender_l = normalize(sender)
    if any(marker in sender_l for marker in BOUNCE_SENDERS) or any(
        marker in haystack for marker in BOUNCE_MARKERS
    ):
        return "bounce"

    if any(marker in haystack for marker in OFFER_MARKERS):
        return "offer"
    # Rejection is checked before interest: a polite rejection often contains
    # the word "role" and other interest-adjacent language.
    if any(marker in haystack for marker in REJECTION_MARKERS):
        return "rejection"
    if any(marker in haystack for marker in AUTO_MARKERS):
        return "auto_ack"
    if any(marker in haystack for marker in INTEREST_MARKERS):
        return "interested"

    if use_llm and env.get("ANTHROPIC_API_KEY"):
        guess = _classify_with_claude(subject, body)
        if guess in CLASSIFICATIONS:
            return guess
    return "other"


def _classify_with_claude(subject: str, body: str) -> str:
    from ..llm.anthropic import API_URL, API_VERSION, DEFAULT_MODEL
    from ..util import http

    prompt = (
        "Classify this reply to a job application. Answer with exactly one word from: "
        "offer, interested, rejection, auto_ack, other.\n\n"
        f"Subject: {subject}\n\n{truncate(body, 3000)}"
    )
    try:
        data = http.post_json(
            API_URL,
            json_body={
                "model": env.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
                "max_tokens": 10,
                "messages": [{"role": "user", "content": prompt}],
            },
            headers={
                "x-api-key": env.require("ANTHROPIC_API_KEY"),
                "anthropic-version": API_VERSION,
            },
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        log.warn(f"reply classification fell back to rules: {exc}")
        return "other"
    blocks = data.get("content", []) if isinstance(data, dict) else []
    text = "".join(b.get("text", "") for b in blocks).strip().lower()
    return re.sub(r"[^a-z_]", "", text)


STATUS_FOR_CLASSIFICATION = {
    "offer": ApplicationStatus.OFFER,
    "interested": ApplicationStatus.INTERVIEW,
    "rejection": ApplicationStatus.REJECTED,
    "auto_ack": None,      # an autoresponder is not a human reply
    "bounce": ApplicationStatus.FAILED,   # it never arrived, so it was never sent
    "other": ApplicationStatus.REPLIED,
}

_BOUNCED_ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def bounced_address(body: str, own_address: str = "") -> str:
    """Pull the address that failed out of a bounce notice.

    The bounce arrives from the mail system, not the company, so it cannot be
    matched by sender. The failed recipient is quoted in the body instead.
    """
    for candidate in _BOUNCED_ADDRESS_RE.findall(body[:3000]):
        lowered = candidate.lower()
        if lowered == (own_address or "").lower():
            continue
        if any(part in lowered for part in ("mailer-daemon", "postmaster", "googlemail", "google.com")):
            continue
        return lowered
    return ""


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return value


def _extract_body(message: email.message.Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        for part in message.walk():
            if part.get_content_type() == "text/html":
                from ..util.text import strip_html

                payload = part.get_payload(decode=True) or b""
                return strip_html(
                    payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                )
        return ""
    payload = message.get_payload(decode=True) or b""
    return payload.decode(message.get_content_charset() or "utf-8", errors="replace")


class InboxReader:
    """Minimal IMAP client. Read only: it never deletes or moves mail."""

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        mailbox: str = "INBOX",
    ) -> None:
        self.host = host or env.get("IMAP_HOST", "imap.gmail.com") or "imap.gmail.com"
        self.port = port or env.get_int("IMAP_PORT", 993)
        self.user = user or env.get("IMAP_USER") or env.get("SENDER_EMAIL", "") or ""
        self.password = (
            password or env.get("IMAP_PASSWORD") or env.get("GMAIL_APP_PASSWORD", "") or ""
        )
        self.mailbox = mailbox

    def ready(self) -> tuple[bool, str]:
        if not self.user:
            return False, "IMAP_USER (or SENDER_EMAIL) is not set"
        if not self.password:
            return False, "IMAP_PASSWORD (or GMAIL_APP_PASSWORD) is not set"
        return True, ""

    def fetch_recent(self, days: int = 14, limit: int = 60) -> list[IncomingMessage]:
        ok, why = self.ready()
        if not ok:
            raise RuntimeError(why)

        from datetime import datetime, timedelta

        since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        messages: list[IncomingMessage] = []
        client = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            client.login(self.user, self.password)
            client.select(self.mailbox, readonly=True)
            status, data = client.search(None, f'(SINCE "{since}")')
            if status != "OK":
                return []
            uids = data[0].split()[-limit:]
            for uid in uids:
                status, payload = client.fetch(uid, "(RFC822)")
                if status != "OK" or not payload or not isinstance(payload[0], tuple):
                    continue
                parsed = email.message_from_bytes(payload[0][1])
                name, addr = parseaddr(_decode(parsed.get("From")))
                messages.append(
                    IncomingMessage(
                        uid=uid.decode(),
                        from_addr=addr.lower(),
                        from_name=name,
                        subject=_decode(parsed.get("Subject")),
                        body=_extract_body(parsed),
                        in_reply_to=(parsed.get("In-Reply-To") or "").strip(),
                        references=(parsed.get("References") or "").strip(),
                    )
                )
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass
        return messages

    @staticmethod
    def match_application(db: Any, message: IncomingMessage) -> Any:
        """Link a reply to the application it answers.

        Threading headers are authoritative. Falling back to the sender address
        catches replies from a colleague the original recipient looped in.
        """
        token = message.in_reply_to or ""
        if token:
            row = db.one(
                "SELECT * FROM applications WHERE message_id = ? LIMIT 1", (token,)
            )
            if row:
                from ..models import Application

                return Application.from_row(row)
        if message.references:
            for reference in message.references.split():
                row = db.one(
                    "SELECT * FROM applications WHERE message_id = ? LIMIT 1", (reference,)
                )
                if row:
                    from ..models import Application

                    return Application.from_row(row)
        by_sender = db.find_application_by_recipient(message.from_addr)
        if by_sender:
            return by_sender
        domain = message.from_addr.split("@")[-1]
        row = db.one(
            "SELECT * FROM applications WHERE recipient_email LIKE ? AND sent_at <> '' "
            "ORDER BY sent_at DESC LIMIT 1",
            (f"%@{domain}",),
        )
        if row:
            from ..models import Application

            return Application.from_row(row)
        return None
