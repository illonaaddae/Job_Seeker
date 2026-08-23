"""Deterministic writer used when no API key is set, or as the Claude fallback.

The hard part is staying specific without a model. It does that by pulling real
material out of the job description itself: the responsibilities the posting
actually lists, the technologies it names that the applicant genuinely has, and
the project in the profile with the highest overlap. Nothing is written from a
fixed sentence bank alone.
"""

from __future__ import annotations

import random
import re
from typing import Any

from ..models import Job
from ..persona import Persona
from ..util.style import enforce
from ..util.text import contains_phrase, normalize, sentences, truncate
from . import user_templates
from .base import Draft

_BULLET_RE = re.compile(r"^\s*[-•*·]\s*(.+)$", re.M)
_RESPONSIBILITY_HINTS = (
    "you will", "you'll", "responsibilities", "what you", "the role", "day to day",
    "your work", "in this role", "we are looking", "we're looking",
)


def _hook_from_description(job: Job, skills: list[str] | None = None) -> str:
    """Find one line in the posting worth quoting back, so the letter is anchored."""
    text = job.description or ""
    if not text:
        return ""

    candidates: list[str] = [b.strip() for b in _BULLET_RE.findall(text)]
    for sentence in sentences(text[:4000]):
        lowered = normalize(sentence)
        if any(hint in lowered for hint in _RESPONSIBILITY_HINTS) and len(sentence.split()) > 6:
            candidates.append(sentence.strip())

    # Prefer a line that names work rather than a benefits or legal line.
    noise = (
        "equal opportunity", "salary", "benefits", "pension", "we offer", "perks",
        "visa", "cookie", "privacy", "diversity statement", "background check",
    )

    def usable(candidate: str, low: int = 8, high: int = 45) -> bool:
        lowered = normalize(candidate)
        if any(word in lowered for word in noise):
            return False
        return low <= len(candidate.split()) <= high

    for candidate in candidates:
        if usable(candidate):
            return truncate(candidate.rstrip(".;,"), 190, suffix="")

    # Nothing structured. Fall back to the first sentence that names a technology
    # the applicant actually has, which is still specific to this posting.
    if skills:
        for sentence in sentences(text[:6000]):
            if usable(sentence, low=6, high=50) and any(
                contains_phrase(sentence, skill) for skill in skills
            ):
                return truncate(sentence.rstrip(".;,"), 190, suffix="")

    # Last resort: the first substantial sentence of the posting.
    for sentence in sentences(text[:3000]):
        if usable(sentence, low=9, high=50):
            return truncate(sentence.rstrip(".;,"), 190, suffix="")
    return ""


def _end(value: str) -> str:
    """Guarantee a sentence ends with terminal punctuation."""
    value = (value or "").strip().rstrip(" ,;:")
    if not value:
        return ""
    return value if value[-1] in ".!?" else value + "."


def _clip(value: str, limit: int) -> str:
    """Trim to whole sentences under `limit`, never mid clause, always punctuated."""
    value = " ".join((value or "").split())
    if not value:
        return ""
    if len(value) <= limit:
        return _end(value)
    kept: list[str] = []
    used = 0
    for sentence in sentences(value):
        if used + len(sentence) > limit and kept:
            break
        kept.append(sentence)
        used += len(sentence) + 1
    if kept:
        return _end(" ".join(kept))
    # A single sentence longer than the limit: cut on a clause boundary instead.
    head = value[:limit]
    for separator in (", ", "; ", " "):
        if separator in head:
            head = head[: head.rfind(separator)]
            break
    return _end(head)


def _as_clause(value: str) -> str:
    """Lowercase the opening word so the text can be embedded mid sentence."""
    value = (value or "").strip()
    if not value:
        return ""
    first, _, rest = value.partition(" ")
    is_acronym = len(first) > 1 and first.isupper()
    lowered = first[0].lower() + first[1:] if first[:1].isupper() and not is_acronym else first
    return (lowered + (" " + rest if rest else "")).rstrip(".")


# A bare industry word can read oddly mid sentence: "software is the kind of
# work I want to be close to" says nothing. These read as a field of work.
_INDUSTRY_PHRASES = {
    "software": "software engineering",
    "technology": "product engineering",
    "software house": "software engineering",
    "software consultancy": "consultancy work",
    "fintech": "fintech",
    "payments": "payments",
    "health tech": "health technology",
    "agritech": "agriculture technology",
    "retail tech": "retail technology",
    "banking": "banking technology",
    "innovation hub": "the startup community here",
    "incubator": "the startup community here",
    "talent": "engineering talent work",
    "commerce": "commerce technology",
    "super app": "consumer product work",
}


def _industry_phrase(industry: str) -> str:
    if not industry:
        return ""
    return _INDUSTRY_PHRASES.get(industry.strip().lower(), industry.strip())


def _clean_hook(hook: str) -> str:
    """Strip the second person framing so the line can be quoted inside a sentence."""
    cleaned = re.sub(r"(?i)^(you will|you'll|you would|the successful candidate will)\s+", "", hook)
    cleaned = re.sub(
        r"(?i)^(we are looking for|we're looking for)\s+(someone|a person)?\s*(to)?\s*", "", cleaned
    )
    return cleaned.strip().rstrip(".;,")


def _skill_phrase(names: list[str], limit: int = 3) -> str:
    picked = names[:limit]
    if not picked:
        return ""
    if len(picked) == 1:
        return picked[0]
    return ", ".join(picked[:-1]) + " and " + picked[-1]


class TemplateWriter:
    name = "template"

    def _values(
        self,
        persona: Persona,
        job: Job,
        contact_name: str,
        skills: list[str],
        hook: str,
        industry: str = "",
    ) -> dict[str, str]:
        """Everything a user written template can refer to."""
        evidence = persona.best_evidence(job.description or job.title, limit=1)
        primary = evidence[0] if evidence else {}
        role = (persona.best_experience(job.description or job.title, limit=1) or [{}])[0]
        education = persona.education[0] if persona.education else {}
        identity = persona.identity
        stack = ", ".join(primary.get("stack", [])[:4])

        return {
            "name": persona.name,
            "first_name": persona.first_name,
            "headline": identity.get("headline", ""),
            "signature": persona.signature(),
            "website": identity.get("website", ""),
            "github": identity.get("github", ""),
            "location": identity.get("location", "").split(",")[0],
            "company": job.company_name,
            "role": job.title.replace(" (speculative)", ""),
            "role_lower": job.title.replace(" (speculative)", "").lower(),
            "location_of_role": job.location,
            "hook": f'The posting describes the work as "{hook}", and that is the part I want.' if hook else "",
            "skills": _skill_phrase(skills) or _skill_phrase(persona.skill_names(("core",))),
            "evidence": f"{primary.get('name', '')} ({stack})" if primary else "",
            "evidence_summary": _clip(primary.get("summary", ""), 200) if primary else "",
            "evidence_link": primary.get("url") or primary.get("repo") or identity.get("website", ""),
            "current_role": role.get("role_short") or role.get("role", ""),
            "current_role_full": role.get("role", ""),
            "current_company": role.get("company", ""),
            "availability": identity.get("availability", ""),
            "current_detail": _clip(_as_clause((role.get("bullets") or [""])[0]), 180),
            "education": education.get("credential", ""),
            "institution": education.get("institution", ""),
            "industry": _industry_phrase(industry),
            "greeting": f"Dear {contact_name}," if contact_name else f"Hello {job.company_name} team,",
        }

    def _from_user_template(
        self,
        template_name: str,
        persona: Persona,
        job: Job,
        contact_name: str,
        skills: list[str],
        hook: str,
        industry: str = "",
    ) -> Draft | None:
        """Use the applicant's own wording when they have written some."""
        template = user_templates.get(template_name)
        if not template:
            return None

        values = self._values(persona, job, contact_name, skills, hook, industry)
        company, role = job.company_name, values["role"]

        body = user_templates.render(template.get("body", ""), values, company=company, role=role)
        if not body.strip():
            return None

        subject = user_templates.render(
            template.get("subject") or "{role} application, {name}", values,
            company=company, role=role,
        )
        # A letter is the email without its greeting and sign off, broken into
        # paragraphs, so the PDF does not repeat what the message already says.
        middle = [p.strip() for p in body.split("\n\n")][1:-1]
        paragraphs = [p for p in middle if p and not p.lower().startswith("best regards")]

        summary, _ = enforce(
            f"{persona.first_name} matches {len(skills)} of the skills this role names.",
            require_specifics=False,
        )
        return Draft(
            subject=subject,
            email_body=body,
            letter_paragraphs=paragraphs or [body],
            tailored_summary=summary,
            generator="your template",
        )

    def write(
        self,
        persona: Persona,
        job: Job,
        *,
        contact_name: str = "",
        matched_skills: list[str] | None = None,
    ) -> Draft:
        skills = matched_skills or [
            s.name for s in persona.matched_skills(job.description or job.title)
        ]
        if job.source == "speculative":
            industry = ""
            match = re.search(r"a ([a-z ]+) company", job.description or "")
            if match:
                industry = match.group(1).strip()
            custom = self._from_user_template(
                "speculative_email", persona, job, contact_name, skills, "", industry
            )
            return custom or self._speculative(persona, job, contact_name, matched_skills)

        hook = _clean_hook(_hook_from_description(job, skills))
        custom = self._from_user_template(
            "application_email", persona, job, contact_name, skills, hook
        )
        return custom or self._for_posting(persona, job, contact_name, matched_skills)

    def _speculative(
        self,
        persona: Persona,
        job: Job,
        contact_name: str,
        matched_skills: list[str] | None,
    ) -> Draft:
        """A cold approach, which is a different letter entirely.

        There is no posting to quote and no role to name, so the letter has to
        do the work a job advert would normally do: say who is writing, why this
        company specifically, and what they would get. It also has to ask a
        question, because a speculative note with no question is just noise.
        """
        role = (persona.targeting.get("roles") or ["Software Engineer"])[0]
        company = job.company_name
        industry = ""
        # The description carries the company's industry from the seed list.
        match = re.search(r"a ([a-z ]+) company", job.description or "")
        if match:
            industry = match.group(1).strip()

        skills = matched_skills or persona.skill_names(("core",))
        skill_phrase = _skill_phrase(skills, limit=3)
        evidence = persona.best_evidence(job.description or company, limit=1)
        primary = evidence[0] if evidence else {}
        current = (persona.best_experience(job.description or company, limit=1) or [{}])[0]
        link = persona.identity.get("website", "")
        greeting = f"Dear {contact_name}," if contact_name else f"Hello {company} team,"

        opening = (
            f"I am writing on the chance that you are hiring, or expect to be. "
            f"I am a {role.lower()} in Accra"
            + (f", and {industry} is the kind of work I want to be close to." if industry else ".")
        )

        current_line = ""
        if current:
            current_line = (
                f"I am currently {current.get('role')} at {current.get('company')}, "
                f"where I {_clip(_as_clause((current.get('bullets') or [''])[0]), 170)}"
            )

        evidence_line = ""
        if primary:
            stack = ", ".join(primary.get("stack", [])[:4])
            evidence_line = (
                f"Outside that I built {primary.get('name')} ({stack}). "
                f"{_clip(primary.get('summary', ''), 190)} It is at {link}."
            )

        ask = (
            f"If there is anything open at {company} that needs "
            + (skill_phrase or "a frontend engineer")
            + ", I would like to be considered. If not, I would still value knowing "
            "what you look for, so I can aim at it."
        )

        body = "\n\n".join(
            part
            for part in [greeting, opening, current_line, evidence_line, ask,
                         "Best regards,\n" + persona.signature()]
            if part
        )

        p1 = f"{opening} I am writing to {company} directly rather than answering a posting."
        p2 = " ".join(part for part in [current_line, evidence_line] if part)
        education = persona.education[0] if persona.education else {}
        p3 = (
            (f"I am studying for a {education.get('credential')} at {education.get('institution')}. "
             if education else "")
            + ask
        )

        subject = f"{role} in Accra, {persona.name}"
        clean_subject, _ = enforce(subject, require_specifics=False)
        clean_body, report = enforce(body, company=company, max_words=260, require_specifics=False)
        paragraphs = [
            enforce(p, company=company, require_specifics=False)[0] for p in (p1, p2, p3) if p.strip()
        ]
        summary, _ = enforce(
            f"Speculative approach to {company}"
            + (f", a {industry} company." if industry else "."),
            require_specifics=False,
        )
        return Draft(
            subject=clean_subject,
            email_body=clean_body,
            letter_paragraphs=paragraphs,
            tailored_summary=summary,
            generator="template",
            style_notes=[] if report.clean else [report.summary()],
        )

    def _for_posting(
        self,
        persona: Persona,
        job: Job,
        contact_name: str = "",
        matched_skills: list[str] | None = None,
    ) -> Draft:
        rng = random.Random(f"{job.company_name}:{job.title}")  # stable per job
        skills = matched_skills or [
            s.name for s in persona.matched_skills(job.description or job.title)
        ]
        skill_phrase = _skill_phrase(skills) or _skill_phrase(persona.skill_names(("core",)))
        evidence = persona.best_evidence(job.description or job.title, limit=2)
        primary = evidence[0] if evidence else {}
        secondary = evidence[1] if len(evidence) > 1 else {}
        role = persona.best_experience(job.description or job.title, limit=1)
        current_role = role[0] if role else {}
        hook = _clean_hook(_hook_from_description(job, skills))
        identity = persona.identity

        greeting = f"Dear {contact_name}," if contact_name else f"Hello {job.company_name} team,"

        # ---------------------------------------------------------- the email
        opening = (
            f"I am applying for the {job.title} role at {job.company_name}."
            if job.url
            else f"I am writing about the {job.title} role at {job.company_name}."
        )
        anchor = (
            f' The posting describes the work as "{hook}", and that is the part I want.'
            if hook
            else f" {job.company_name} is building the kind of product I want to work on."
        )

        project_link = primary.get("url") or primary.get("repo") or identity.get("website", "")
        project_line = ""
        if primary:
            stack = ", ".join(primary.get("stack", [])[:4])
            project_line = (
                f"The closest thing I have built is {primary.get('name')} "
                f"({stack}). {_clip(primary.get('summary', ''), 200)} "
                f"You can see it at {project_link}."
            )

        work_line = ""
        if current_role:
            bullet = _as_clause((current_role.get("bullets") or [""])[0])
            work_line = (
                f"I am currently {current_role.get('role')} at {current_role.get('company')}, "
                f"where I {_clip(bullet, 180)}"
            )

        skills_line = (
            f"On your stack, I work in {skill_phrase} day to day."
            if skill_phrase
            else ""
        )

        closing = rng.choice(
            [
                "If the role is still open, I would like fifteen minutes to talk about it.",
                "If this is still open, I am happy to walk through any of the above on a call.",
                "If you are still reviewing applications, I would welcome a short conversation.",
            ]
        )

        email_body = "\n\n".join(
            part
            for part in [
                greeting,
                opening + anchor,
                " ".join(p for p in [work_line, skills_line] if p),
                project_line,
                closing,
                "Best regards,\n" + persona.signature(),
            ]
            if part
        )

        # --------------------------------------------------------- the letter
        p1 = (
            f"I am applying for the {job.title} role at {job.company_name}. "
            + (f'Your posting describes the work as "{hook}". ' if hook else "")
            + (
                f"I work in {skill_phrase}, and that is the work I want to be doing next."
                if skill_phrase
                else "That is the work I want to be doing next."
            )
        )

        p2_parts = []
        if work_line:
            p2_parts.append(_end(work_line))
        if primary:
            highlight = (primary.get("highlights") or [""])[0]
            p2_parts.append(
                f"Outside that, I built {primary.get('name')}: "
                f"{_clip(_as_clause(primary.get('summary', '')), 230)} "
                + (f"{_end(highlight)} " if highlight else "")
                + (f"It is live at {project_link}." if project_link else "")
            )
        if secondary:
            p2_parts.append(
                f"I have also shipped {secondary.get('name')}: "
                f"{_clip(_as_clause(secondary.get('summary', '')), 160)}"
            )
        p2 = " ".join(p2_parts)

        education = persona.education[0] if persona.education else {}
        p3 = (
            (
                f"I am studying for a {education.get('credential')} at {education.get('institution')}, "
                if education
                else ""
            )
            + (
                f"and I hold the {persona.certifications[0].get('name')}. "
                if persona.certifications
                else ""
            )
            + persona.narrative.get(
                "why_me_closing",
                "I would welcome the chance to talk about where I could add the most value.",
            )
        )

        subject = f"{job.title} application, {persona.name}"
        if len(subject) > 78:
            subject = truncate(subject, 78, suffix="")

        clean_subject, _ = enforce(subject, require_specifics=False)
        clean_body, body_report = enforce(
            email_body, company=job.company_name, job_title=job.title, max_words=260
        )
        paragraphs = [
            enforce(p, company=job.company_name, job_title=job.title, require_specifics=False)[0]
            for p in (p1, p2, p3)
            if p.strip()
        ]
        summary, _ = enforce(
            f"{persona.first_name} matches {len(skills)} of the skills this role names"
            + (f", closest work: {primary.get('name')}." if primary else "."),
            require_specifics=False,
        )

        return Draft(
            subject=clean_subject,
            email_body=clean_body,
            letter_paragraphs=paragraphs,
            tailored_summary=summary,
            generator="template",
            style_notes=[] if body_report.clean else [body_report.summary()],
        )
