"""Domain objects. Plain dataclasses so they serialise cleanly to JSON and SQLite."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Self


def utcnow() -> str:
    """ISO-8601 UTC timestamp — the only time format stored anywhere."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class JobStatus(StrEnum):
    NEW = "new"           # discovered, not yet scored
    SCORED = "scored"     # scored, awaiting a decision
    SHORTLISTED = "shortlisted"
    DRAFTED = "drafted"   # documents generated
    APPLIED = "applied"
    REJECTED_BY_ME = "rejected_by_me"
    EXPIRED = "expired"


class ApplicationStatus(StrEnum):
    DRAFT = "draft"           # documents generated, not approved
    APPROVED = "approved"     # human said yes — safe to send
    SENT = "sent"
    FAILED = "failed"
    REPLIED = "replied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    GHOSTED = "ghosted"
    WITHDRAWN = "withdrawn"


TERMINAL_STATUSES = {
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
}


class Channel(StrEnum):
    EMAIL = "email"        # cold email to a contact
    PORTAL = "portal"      # apply on the company's ATS page (human finishes it)
    REFERRAL = "referral"


class _Base:
    """Shared (de)serialisation for all record dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def field_names(cls) -> list[str]:
        return [f.name for f in fields(cls)]  # type: ignore[arg-type]

    @classmethod
    def from_row(cls, row: Any) -> Self:
        data = dict(row)
        known = set(cls.field_names())
        payload: dict[str, Any] = {}
        for key, value in data.items():
            if key not in known:
                continue
            if key.endswith("_json") or key in {"score_breakdown", "tags", "keywords"}:
                payload[key] = json.loads(value) if isinstance(value, str) and value else (value or [])
            else:
                payload[key] = value
        return cls(**payload)  # type: ignore[arg-type]


@dataclass(slots=True)
class Company(_Base):
    name: str
    domain: str = ""
    website: str = ""
    careers_url: str = ""
    source: str = ""
    industry: str = ""
    location: str = ""
    notes: str = ""
    id: int | None = None
    created_at: str = field(default_factory=utcnow)


@dataclass(slots=True)
class Job(_Base):
    title: str
    company_name: str
    source: str
    external_id: str
    url: str = ""
    location: str = ""
    remote: int = 0
    employment_type: str = ""
    department: str = ""
    description: str = ""
    salary: str = ""
    posted_at: str = ""
    company_id: int | None = None
    score: float = 0.0
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    status: str = JobStatus.NEW
    id: int | None = None
    discovered_at: str = field(default_factory=utcnow)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.external_id}"


@dataclass(slots=True)
class Contact(_Base):
    company_id: int
    email: str
    name: str = ""
    title: str = ""
    linkedin: str = ""
    source: str = ""
    confidence: int = 0
    verified: int = 0
    id: int | None = None
    created_at: str = field(default_factory=utcnow)


@dataclass(slots=True)
class Application(_Base):
    job_id: int
    company_id: int | None = None
    contact_id: int | None = None
    channel: str = Channel.EMAIL
    status: str = ApplicationStatus.DRAFT
    recipient_email: str = ""
    subject: str = ""
    body: str = ""
    cover_letter_path: str = ""
    cv_path: str = ""
    tailored_summary: str = ""
    message_id: str = ""
    thread_refs: str = ""
    generator: str = ""
    form_answers: str = ""
    sent_at: str = ""
    notes: str = ""
    id: int | None = None
    created_at: str = field(default_factory=utcnow)
    updated_at: str = field(default_factory=utcnow)


@dataclass(slots=True)
class Followup(_Base):
    application_id: int
    sequence_no: int
    due_at: str
    status: str = "pending"       # pending | sent | cancelled
    sent_at: str = ""
    message_id: str = ""
    id: int | None = None


@dataclass(slots=True)
class Reply(_Base):
    application_id: int | None
    from_addr: str
    subject: str = ""
    snippet: str = ""
    classification: str = "unknown"   # interested | rejection | auto_ack | other
    received_at: str = field(default_factory=utcnow)
    uid: str = ""
    message_id: str = ""
    draft_subject: str = ""
    draft_body: str = ""
    draft_status: str = "none"        # none | draft | approved | sent
    draft_generator: str = ""
    responded_at: str = ""
    id: int | None = None


@dataclass(slots=True)
class Event(_Base):
    type: str
    message: str = ""
    job_id: int | None = None
    application_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    created_at: str = field(default_factory=utcnow)
