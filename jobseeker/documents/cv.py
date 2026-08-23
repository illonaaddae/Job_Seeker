"""CV rendering, optionally re-ordered for a specific job.

Two modes:

* `build_cv(persona)` renders the master CV from the profile.
* `build_cv(persona, job=...)` renders a tailored copy where the skills line
  leads with what this job asked for, and the projects are ordered by relevance
  to the posting. The facts never change, only their order, which is the line
  between tailoring and lying.
"""

from __future__ import annotations

from pathlib import Path

from ..models import Job
from ..persona import Persona
from ..util.style import sanitise
from ..util.text import slugify
from .pdf import Document


def _ordered_skills(persona: Persona, job: Job | None) -> list[str]:
    core = persona.skill_names(("core",))
    secondary = persona.skill_names(("secondary",))
    if not job:
        return core + secondary
    matched = [s.name for s in persona.matched_skills(job.description or job.title)]
    rest = [name for name in core + secondary if name not in matched]
    return matched + rest


def build_cv(
    persona: Persona,
    job: Job | None = None,
    output_dir: str | Path = "generated/cv",
) -> Path:
    identity = persona.identity
    doc = Document(margins=(50, 50, 50, 50))
    doc.title = f"CV, {persona.name}"
    doc.author = persona.name

    doc.paragraph(persona.name, "name")
    doc.paragraph(sanitise(identity.get("headline", "")), "tagline")
    doc.paragraph(
        " | ".join(
            part
            for part in [
                identity.get("email", ""),
                identity.get("phone", ""),
                identity.get("location", ""),
                identity.get("website", "").replace("https://", ""),
                identity.get("github", "").replace("https://", ""),
                identity.get("linkedin", "").replace("https://www.", ""),
            ]
            if part
        ),
        "contact",
    )
    doc.accent_bar()

    summary = persona.narrative.get("summary", "")
    if summary:
        doc.heading("Profile")
        doc.paragraph(sanitise(summary), "body")

    doc.heading("Skills")
    ordered = _ordered_skills(persona, job)
    doc.paragraph(", ".join(ordered), "body", space_after=4)
    soft = persona.data.get("skills", {}).get("soft", [])
    if soft:
        doc.paragraph("Also: " + ", ".join(soft), "small")

    doc.heading("Experience")
    for role in persona.experience:
        doc.key_value_row(
            f"{role.get('role')}, {role.get('company')}",
            f"{role.get('period')}  {role.get('location', '')}".strip(),
        )
        doc.bullets([sanitise(b) for b in role.get("bullets", [])])
        doc.spacer(2)

    doc.heading("Selected projects")
    projects = (
        persona.best_evidence(job.description or job.title, limit=4)
        if job
        else persona.projects[:4]
    )
    for project in projects:
        link = project.get("url") or project.get("repo") or ""
        doc.key_value_row(project.get("name", ""), link.replace("https://", ""))
        doc.paragraph(sanitise(project.get("summary", "")), "small", space_after=2)
        stack = ", ".join(project.get("stack", []))
        if stack:
            doc.paragraph(f"Stack: {stack}", "small")
        doc.spacer(2)

    doc.heading("Education")
    for entry in persona.education:
        doc.key_value_row(
            f"{entry.get('credential')}, {entry.get('institution')}",
            entry.get("period", ""),
        )
        if entry.get("note"):
            doc.paragraph(sanitise(entry["note"]), "small")

    if persona.certifications:
        doc.heading("Certifications")
        doc.bullets(
            [f"{c.get('name')}, {c.get('issuer')} ({c.get('year')})" for c in persona.certifications]
        )

    suffix = f"-for-{slugify(job.company_name, 24)}" if job else ""
    filename = f"{slugify(persona.name, 30)}-cv{suffix}.pdf"
    return doc.save(Path(output_dir) / filename)
