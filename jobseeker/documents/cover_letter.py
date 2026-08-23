"""Cover letter PDF: letterhead, date, recipient block, body, sign off.

Layout is deliberately plain. Recruiters read these in ten seconds, so the job
of the design is to get out of the way: one accent rule, a clear hierarchy, and
no decoration that competes with the words.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..llm.base import Draft
from ..models import Job
from ..persona import Persona
from ..util.style import sanitise
from ..util.text import slugify
from .pdf import Document


def build_cover_letter(
    persona: Persona,
    job: Job,
    draft: Draft,
    output_dir: str | Path = "generated/letters",
    *,
    recipient_name: str = "",
    company_address: str = "",
) -> Path:
    """Render the drafted letter to a one page PDF and return its path."""
    identity = persona.identity
    doc = Document()
    doc.title = f"Cover letter, {job.title} at {job.company_name}"
    doc.author = persona.name

    # Letterhead
    doc.paragraph(persona.name, "name")
    doc.paragraph(sanitise(identity.get("headline", "")), "tagline")
    contact_line = " | ".join(
        part
        for part in [
            identity.get("email", ""),
            identity.get("phone", ""),
            identity.get("website", "").replace("https://", ""),
            identity.get("github", "").replace("https://", ""),
            identity.get("location", ""),
        ]
        if part
    )
    doc.paragraph(contact_line, "contact")
    doc.accent_bar()

    # Date and recipient
    doc.paragraph(date.today().strftime("%d %B %Y"), "meta")
    recipient_block = [job.company_name]
    if company_address:
        recipient_block.append(company_address)
    doc.paragraph("\n".join(recipient_block), "meta")
    doc.spacer(6)

    # The location often already carries brackets, so only add our own when it does not.
    location_suffix = ""
    if job.location:
        location_suffix = (
            f" {job.location}" if job.location.strip().startswith("(") else f" ({job.location})"
        )
    doc.paragraph(f"Re: {job.title}{location_suffix}", "h2")

    greeting = f"Dear {recipient_name}," if recipient_name else "Dear Hiring Team,"
    doc.paragraph(greeting, "body", space_after=6, align="left")

    for paragraph in draft.letter_paragraphs:
        doc.paragraph(sanitise(paragraph), "body")

    if job.url:
        doc.paragraph(f"Role reference: {job.url}", "small")

    doc.spacer(6)
    doc.paragraph("Yours sincerely,", "sign", space_after=18)
    doc.paragraph(persona.name, "sign", space_after=2)
    doc.paragraph(sanitise(identity.get("headline", "")), "small")

    filename = (
        f"{slugify(persona.name, 30)}-cover-letter-"
        f"{slugify(job.company_name, 28)}-{slugify(job.title, 28)}.pdf"
    )
    return doc.save(Path(output_dir) / filename)
