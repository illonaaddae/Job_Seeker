"""Answers to the free text questions application forms keep asking.

Every ATS form asks a handful of the same things in slightly different words.
The answers live in `data/answers.json` and are the applicant's own, which
matters: these are the parts of an application that are supposed to sound like
a person rather than a document.

Two levels of tailoring:

* Without a model, the stored answer is rendered with the job's details filled
  in. It is true, specific and ready to paste.
* With a funded Anthropic key, the answer is rewritten against this particular
  job description, keeping the same facts and the same voice.

The stored answer is always the fallback, so a failed or unfunded API degrades
to something usable rather than to nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import Job
from ..persona import Persona
from ..util import env, log
from ..util.style import enforce, style_prompt_block
from ..util.text import truncate
from . import user_templates

DEFAULT_PATH = "data/answers.json"

# Questions that must never be answered by a machine on the applicant's behalf,
# because a wrong answer is a lie rather than a weak sentence.
NEVER_GENERATE = {"salary"}


def bank_version(path: str | Path = DEFAULT_PATH) -> str:
    """A fingerprint of the answer bank.

    Answers are cached per application so the wording does not drift between
    visits. Without a version to compare against, an edit to answers.json would
    never reach an application that had already been opened, which is a silent
    and very confusing failure.
    """
    file_path = Path(path)
    if not file_path.exists():
        return "none"
    import hashlib

    return hashlib.sha256(file_path.read_bytes()).hexdigest()[:12]


def load(path: str | Path = DEFAULT_PATH) -> dict[str, dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warn(f"answers file is not valid JSON, ignoring it: {exc}")
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and not k.startswith("_")}


def _values(persona: Persona, job: Job) -> dict[str, str]:
    """The same placeholders templates use, plus a plainer form of the hook."""
    from .templates import TemplateWriter, _clean_hook, _hook_from_description

    skills = [s.name for s in persona.matched_skills(job.description or job.title)]
    hook = _clean_hook(_hook_from_description(job, skills))
    values = TemplateWriter()._values(persona, job, "", skills, hook)
    # The templated hook is a full quoted sentence, which reads oddly inside an
    # answer, so a plainer version is offered alongside it.
    # Quoted verbatim: lowercasing the line mangles the technology names in it,
    # and "react and typescript" in an application reads as carelessness.
    values["hook_plain"] = (
        f'the posting describes the work as "{hook}".' if hook else "of the work itself."
    )
    return values


def _rewrite_with_claude(
    persona: Persona, job: Job, key: str, question: str, stored: str
) -> str | None:
    from ..util import http
    from .anthropic import API_URL, API_VERSION, DEFAULT_MODEL, is_available, mark_unusable_if_permanent

    if not is_available():
        return None

    system = (
        f"You are {persona.name}, answering a question on a job application form. "
        "You are given her own answer, already true and in her voice. Rewrite it so "
        "it speaks to this specific role, keeping every fact exactly as given. Do not "
        "invent experience, numbers, technologies or employers. Do not make it longer. "
        "If the stored answer already fits, return it close to unchanged.\n\n"
        + style_prompt_block()
        + "\nReturn only the answer text, with no preamble and no quotation marks."
    )
    user = "\n".join(
        [
            f"THE QUESTION: {question}",
            "",
            f"THE ROLE: {job.title} at {job.company_name}",
            "JOB DESCRIPTION:",
            truncate(job.description or "No description was published.", 5000, suffix=""),
            "",
            "HER OWN ANSWER, to be kept true:",
            stored,
            "",
            "ABOUT HER:",
            persona.prompt_context(job.description or job.title),
        ]
    )

    try:
        data = http.post_json(
            API_URL,
            json_body={
                "model": env.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
                "max_tokens": 900,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            headers={
                "x-api-key": env.require("ANTHROPIC_API_KEY"),
                "anthropic-version": API_VERSION,
            },
            timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        mark_unusable_if_permanent(exc)
        log.warn(f"answer for '{key}' fell back to your stored version: {exc}")
        return None

    blocks = data.get("content", []) if isinstance(data, dict) else []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    return text or None


def build(
    persona: Persona,
    job: Job,
    *,
    tailor: bool = True,
    path: str | Path = DEFAULT_PATH,
) -> list[dict[str, Any]]:
    """Return every stored answer, filled in and optionally tailored."""
    bank = load(path)
    if not bank:
        return []

    values = _values(persona, job)
    answers: list[dict[str, Any]] = []

    for key, entry in bank.items():
        stored = entry.get("answer", "")
        if not stored.strip():
            continue

        rendered = user_templates.render(
            stored, values, company=job.company_name, role=job.title
        )

        source = "yours"
        if tailor and key not in NEVER_GENERATE:
            rewritten = _rewrite_with_claude(
                persona, job, key, entry.get("question", key), rendered
            )
            if rewritten:
                cleaned, report = enforce(
                    rewritten, company=job.company_name, job_title=job.title,
                    require_specifics=False,
                )
                if cleaned:
                    rendered, source = cleaned, "tailored"
                    if report.banned:
                        log.dim(f"answer '{key}' still had filler: {report.summary()}")

        answers.append(
            {
                "version": bank_version(path),
                "key": key,
                "question": entry.get("question", key),
                "asked_as": entry.get("asked_as", []),
                "answer": rendered,
                "words": len(rendered.split()),
                "source": source,
            }
        )

    return answers
