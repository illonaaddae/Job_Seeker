"""Writer interface shared by the Claude and template generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models import Job
from ..persona import Persona


@dataclass(slots=True)
class Draft:
    """One complete application package, ready for review."""

    subject: str
    email_body: str
    letter_paragraphs: list[str]
    tailored_summary: str = ""
    generator: str = ""
    style_notes: list[str] = field(default_factory=list)
    tokens_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "email_body": self.email_body,
            "letter_paragraphs": self.letter_paragraphs,
            "tailored_summary": self.tailored_summary,
            "generator": self.generator,
            "style_notes": self.style_notes,
            "tokens_used": self.tokens_used,
        }


class Writer(Protocol):
    name: str

    def write(
        self,
        persona: Persona,
        job: Job,
        *,
        contact_name: str = "",
        matched_skills: list[str] | None = None,
    ) -> Draft: ...
