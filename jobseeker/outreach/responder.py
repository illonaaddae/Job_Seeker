"""Answering the people who reply.

A cold outreach system that cannot hold a conversation wastes the only thing it
earns. When a recruiter writes back, this drafts the answer in the applicant's
voice, using the job and the original application as context.

Two deliberate limits:

* Only the easy half is automated. Interest and scheduling get a real draft.
  Rejections get a short, gracious close, never an argument. Anything the model
  is unsure about is left for a human.
* Auto sending is opt in and, even then, refuses to send anything that commits
  the applicant to a time, a salary figure or an offer decision. Those need a
  person, and the draft is queued instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Application, Job, Reply
from ..persona import Persona
from ..util import env, log
from ..util.style import enforce, style_prompt_block
from ..util.text import truncate

# Phrases that mean the reply is asking for a commitment. A machine should not
# be the thing that answers these.
COMMITMENT_MARKERS = (
    "salary", "compensation", "rate", "notice period", "start date",
    "offer", "contract", "visa", "relocation", "references",
    "availability", "what time", "which day", "book a slot", "calendly",
    "confirm the time", "are you free",
)


@dataclass(slots=True)
class ReplyDraft:
    subject: str
    body: str
    generator: str
    needs_human: bool
    reason: str = ""


def needs_a_person(reply: Reply) -> tuple[bool, str]:
    """Decide whether this reply is safe to answer automatically."""
    haystack = f"{reply.subject}\n{reply.snippet}".lower()
    for marker in COMMITMENT_MARKERS:
        if marker in haystack:
            return True, f"the message asks about {marker}"
    if reply.classification == "offer":
        return True, "an offer should never be answered by a machine"
    return False, ""


def _system_prompt(persona: Persona) -> str:
    return (
        f"You are writing a short email reply as {persona.name}, in the first "
        f"person, as if you are her. Never mention being an AI.\n\n"
        f"Voice: {persona.outreach.get('tone', 'direct and specific')}\n\n"
        + style_prompt_block()
        + "\nReturn only the body of the email. No subject line, no preamble, no "
        "markdown. Keep it under 120 words. End with her name on its own line."
    )


def _user_prompt(persona: Persona, reply: Reply, job: Job | None) -> str:
    context = [
        "THEY WROTE:",
        f"From: {reply.from_addr}",
        f"Subject: {reply.subject}",
        truncate(reply.snippet, 1500),
        "",
        f"This was classified as: {reply.classification}",
    ]
    if job:
        context += [
            "",
            "THE ROLE THIS IS ABOUT:",
            f"{job.title} at {job.company_name}",
            truncate(job.description, 1200),
        ]
    context += [
        "",
        "ABOUT YOU:",
        persona.prompt_context(job.description if job else ""),
        "",
        "TASK:",
    ]

    if reply.classification == "rejection":
        context.append(
            "They have said no. Reply in two or three sentences: thank them "
            "plainly, say you would welcome being considered again later, and "
            "leave it there. Do not argue, do not ask why, do not pitch again."
        )
    elif reply.classification == "interested":
        context.append(
            "They are interested. Say yes warmly and concretely. Confirm you "
            "would like to talk, name what you can bring to the specific role, "
            "and ask what they need from you next. Do not propose a specific "
            "time or date, and do not discuss salary."
        )
    else:
        context.append(
            "Answer the question they actually asked, briefly. If they asked "
            "for something you cannot know, say you will follow up with it."
        )
    return "\n".join(context)


def draft_reply(
    persona: Persona,
    reply: Reply,
    job: Job | None = None,
    application: Application | None = None,
) -> ReplyDraft:
    """Write the response. Falls back to a safe template when no model is set."""
    blocked, reason = needs_a_person(reply)
    subject = reply.subject if reply.subject.lower().startswith("re:") else f"Re: {reply.subject}"

    from ..llm.anthropic import AnthropicWriter, is_available, mark_unusable_if_permanent

    if is_available():
        writer = AnthropicWriter()
        try:
            raw, _ = writer._call(_system_prompt(persona), _user_prompt(persona, reply, job))
            body, report = enforce(raw.strip(), require_specifics=False, max_words=180)
            if body:
                return ReplyDraft(
                    subject=enforce(subject, require_specifics=False)[0],
                    body=body,
                    generator=f"claude:{writer.model}",
                    needs_human=blocked,
                    reason=reason or ("; ".join(report.banned) if report.banned else ""),
                )
        except Exception as exc:  # noqa: BLE001
            mark_unusable_if_permanent(exc)
            log.warn(f"reply drafting fell back to the template: {exc}")

    return _template_reply(persona, reply, job, subject, blocked, reason)


def _template_reply(
    persona: Persona,
    reply: Reply,
    job: Job | None,
    subject: str,
    blocked: bool,
    reason: str,
) -> ReplyDraft:
    """Deterministic fallback. Short, safe and never presumptuous."""
    name = _first_name_of(reply)
    greeting = f"Hello {name}," if name else "Hello,"
    role = f"the {job.title} role at {job.company_name}" if job else "the role"
    link = persona.identity.get("website", "")

    if reply.classification == "rejection":
        body = (
            f"{greeting}\n\n"
            f"Thank you for letting me know, and for taking the time to look at my "
            f"application for {role}.\n\n"
            f"If something opens up later that fits me better, I would be glad to be "
            f"considered.\n\n"
            f"Best regards,\n{persona.name}"
        )
    elif reply.classification == "interested":
        body = (
            f"{greeting}\n\n"
            f"Thank you for getting back to me. I would very much like to talk about "
            f"{role}.\n\n"
            f"My recent work is at {link} if it is useful before we speak. Let me know "
            f"what you need from me next and I will send it over.\n\n"
            f"Best regards,\n{persona.name}"
        )
    else:
        body = (
            f"{greeting}\n\n"
            f"Thank you for your message about {role}. I am happy to help with whatever "
            f"you need from my side.\n\n"
            f"Best regards,\n{persona.name}"
        )

    clean_body, _ = enforce(body, require_specifics=False)
    return ReplyDraft(
        subject=enforce(subject, require_specifics=False)[0],
        body=clean_body,
        generator="template",
        needs_human=blocked,
        reason=reason,
    )


def _first_name_of(reply: Reply) -> str:
    """Pull a usable first name out of the sender address or the sign off."""
    local = reply.from_addr.split("@")[0]
    if "." in local:
        candidate = local.split(".")[0]
    elif local.isalpha() and len(local) > 2:
        candidate = local
    else:
        candidate = ""
    if candidate.lower() in {"careers", "jobs", "hr", "info", "hello", "recruiting", "talent", "noreply"}:
        return ""
    return candidate.capitalize() if candidate.isalpha() else ""


def auto_send_allowed(draft: ReplyDraft) -> tuple[bool, str]:
    """The final gate before a machine written reply leaves the building."""
    mode = (env.get("AUTO_REPLY", "draft") or "draft").strip().lower()
    if mode not in {"off", "draft", "send"}:
        mode = "draft"
    if mode == "off":
        return False, "AUTO_REPLY is off"
    if mode == "draft":
        return False, "AUTO_REPLY is set to draft, so a person approves each one"
    if draft.needs_human:
        return False, draft.reason or "this reply needs a person"
    if re.search(r"\b(\d{1,2}[:.]\d{2}|monday|tuesday|wednesday|thursday|friday)\b", draft.body, re.I):
        return False, "the draft names a time or a day, which a person should confirm"
    return True, ""
