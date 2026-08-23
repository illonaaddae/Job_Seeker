"""Claude backed drafting.

Calls the Anthropic Messages API directly over HTTP so the project keeps its
zero dependency promise. The model is given the profile, the job description
and the house style rules, and is required to return JSON. Whatever comes back
is still passed through the style guard, and a draft that fails the guard is
regenerated once with the specific failures quoted back to the model.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from ..models import Job
from ..persona import Persona
from ..util import env, http, log
from ..util.style import enforce, style_prompt_block
from ..util.text import truncate
from .base import Draft

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"
MAX_JD_CHARS = 9000


# Once the API says the key cannot be used at all, such as an exhausted credit
# balance or a revoked key, every further call fails the same way. Remembering
# that turns a hundred failing requests into one.
#
# It expires, though. A balance gets topped up, and a long running service that
# refused to try again until it was restarted would keep writing from templates
# hours after the problem was fixed, with nothing on screen to explain why.
_UNUSABLE_FOR_SECONDS = 900
_API_UNUSABLE: list[float] = [0.0]


def is_available() -> bool:
    if not env.get("ANTHROPIC_API_KEY"):
        return False
    if not _API_UNUSABLE[0]:
        return True
    if time.time() - _API_UNUSABLE[0] > _UNUSABLE_FOR_SECONDS:
        # Enough time has passed that the cause may be fixed. Try once more.
        _API_UNUSABLE[0] = 0.0
        log.info("retrying the Anthropic API after an earlier failure")
        return True
    return False
_UNUSABLE_MARKERS = (
    "credit balance is too low",
    "invalid x-api-key",
    "authentication_error",
    "permission_error",
)


def mark_unusable_if_permanent(error: Exception) -> bool:
    text = str(error).lower()
    if any(marker in text for marker in _UNUSABLE_MARKERS):
        _API_UNUSABLE[0] = time.time()
        return True
    return False


RESPONSE_SHAPE = {
    "subject": "email subject line, under 78 characters, names the role and the applicant",
    "email_body": "the full email body including greeting and sign off, under 200 words",
    "letter_paragraphs": [
        "cover letter paragraph 1",
        "cover letter paragraph 2",
        "cover letter paragraph 3",
    ],
    "tailored_summary": "one sentence, why this specific match is worth the reader's time",
}


class AnthropicWriter:
    name = "claude"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or env.get("ANTHROPIC_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL
        self.api_key = env.require("ANTHROPIC_API_KEY")
        self.max_tokens = env.get_int("ANTHROPIC_MAX_TOKENS", 2000)

    # ------------------------------------------------------------------ api

    def _call(self, system: str, user: str) -> tuple[str, int]:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = http.post_json(
            API_URL,
            json_body=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": API_VERSION,
            },
            timeout=90,
            retries=3,
        )
        blocks = data.get("content", []) if isinstance(data, dict) else []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        return text, tokens

    # --------------------------------------------------------------- prompts

    def _system_prompt(self, persona: Persona) -> str:
        return (
            f"You write job applications as {persona.name}, in the first person, as if you "
            f"are her. You are not an assistant writing on her behalf and you never mention "
            f"being an AI.\n\n"
            f"Voice: {persona.outreach.get('tone', 'direct and specific')}\n\n"
            + style_prompt_block()
            + "\nReturn only a single JSON object matching this shape, no prose around it:\n"
            + json.dumps(RESPONSE_SHAPE, indent=2)
        )

    def _user_prompt(
        self,
        persona: Persona,
        job: Job,
        contact_name: str,
        matched_skills: list[str],
        retry_notes: str = "",
    ) -> str:
        greeting_target = contact_name or "the hiring team"
        parts = [
            "THE JOB",
            f"Title: {job.title}",
            f"Company: {job.company_name}",
            f"Location: {job.location or 'not stated'}"
            + (" (remote friendly)" if job.remote else ""),
            f"Link: {job.url}" if job.url else "",
            "",
            "JOB DESCRIPTION (verbatim, quote details from it):",
            truncate(job.description or "No description was published.", MAX_JD_CHARS, suffix=""),
            "",
            "THE APPLICANT",
            persona.prompt_context(job.description or job.title),
            "",
            f"Skills this job asks for that she genuinely has: {', '.join(matched_skills) or 'none detected'}",
            "",
            "TASK",
            f"Write the email to {greeting_target} and a three paragraph cover letter.",
            "The email and the letter must not be the same text. The email is the short "
            "version that earns a reply. The letter is the evidence.",
            "Paragraph 1 of the letter: the specific role, and the specific thing about this "
            "job or company that made her apply, drawn from the description above.",
            "Paragraph 2: the strongest matching evidence from her own work, with a concrete "
            "detail such as a technology, a number or a link.",
            "Paragraph 3: what she wants next, in one or two plain sentences.",
        ]
        if retry_notes:
            parts += [
                "",
                "YOUR PREVIOUS ATTEMPT WAS REJECTED. Fix exactly these problems and keep "
                "everything else:",
                retry_notes,
            ]
        return "\n".join(p for p in parts if p != "")

    # ---------------------------------------------------------------- output

    @staticmethod
    def _parse(text: str) -> dict[str, Any]:
        """Pull the JSON object out of the response, tolerating stray prose."""
        cleaned = text.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
        if fence:
            cleaned = fence.group(1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start >= 0 and end > start:
                return json.loads(cleaned[start : end + 1])
            raise

    def write(
        self,
        persona: Persona,
        job: Job,
        *,
        contact_name: str = "",
        matched_skills: list[str] | None = None,
    ) -> Draft:
        skills = matched_skills or [s.name for s in persona.matched_skills(job.description)]
        system = self._system_prompt(persona)
        total_tokens = 0
        retry_notes = ""

        for attempt in range(2):
            user = self._user_prompt(persona, job, contact_name, skills, retry_notes)
            try:
                raw, tokens = self._call(system, user)
            except Exception as exc:  # noqa: BLE001 - any API failure must not lose the draft
                if mark_unusable_if_permanent(exc):
                    log.warn(
                        "The Anthropic API cannot be used, so letters will be written by "
                        f"the template writer for the rest of this run: {exc}"
                    )
                else:
                    log.warn(f"Claude call failed, falling back to the template writer: {exc}")
                break

            total_tokens += tokens
            try:
                payload = self._parse(raw)
            except json.JSONDecodeError:
                log.warn("Claude returned unparseable JSON, falling back to the template writer")
                break

            subject, subject_report = enforce(
                str(payload.get("subject", "")), require_specifics=False
            )
            body, body_report = enforce(
                str(payload.get("email_body", "")),
                company=job.company_name,
                job_title=job.title,
                max_words=230,
            )
            paragraphs = [
                enforce(str(p), company=job.company_name, job_title=job.title,
                        require_specifics=False)[0]
                for p in payload.get("letter_paragraphs", [])
                if str(p).strip()
            ]
            summary, _ = enforce(str(payload.get("tailored_summary", "")), require_specifics=False)

            problems = []
            if not body_report.clean:
                problems.append(f"The email body: {body_report.summary()}.")
            if len(paragraphs) < 2:
                problems.append("The letter needs at least three paragraphs.")
            if subject_report.dashes or subject_report.banned:
                problems.append(f"The subject line: {subject_report.summary()}.")

            if not problems or attempt == 1:
                if problems:
                    log.warn("Draft still imperfect after one retry: " + " ".join(problems))
                return Draft(
                    subject=subject,
                    email_body=body,
                    letter_paragraphs=paragraphs,
                    tailored_summary=summary,
                    generator=f"claude:{self.model}",
                    style_notes=problems,
                    tokens_used=total_tokens,
                )
            retry_notes = " ".join(problems)
            log.dim(f"regenerating draft for {job.company_name}: {retry_notes}")

        from .templates import TemplateWriter

        fallback = TemplateWriter().write(
            persona, job, contact_name=contact_name, matched_skills=skills
        )
        fallback.generator = "template (claude fallback)"
        fallback.tokens_used = total_tokens
        return fallback
