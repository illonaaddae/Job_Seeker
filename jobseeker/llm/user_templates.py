"""Editable message templates.

Every word this system sends should be changeable without touching code. These
templates live in `data/templates.json`, are rendered with a forgiving
formatter, and always pass through the house style guard afterwards, so an edit
cannot smuggle in an em dash or a stock phrase.

A template is optional. Anything left blank falls back to the built in writer,
which composes from the job description rather than a fixed shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from string import Formatter
from typing import Any

from ..util import log
from ..util.style import enforce

DEFAULT_PATH = "data/templates.json"

# Every placeholder a template may use, with a description shown in the editor.
VARIABLES: dict[str, str] = {
    "name": "Your full name",
    "first_name": "Your first name",
    "headline": "Your headline, for example Frontend Engineer, React and TypeScript",
    "signature": "Your full sign off block, name, title, links and phone",
    "website": "Your portfolio URL",
    "github": "Your GitHub URL",
    "location": "Your location",
    "company": "The company being written to",
    "role": "The job title",
    "role_lower": "The job title in lower case, for mid sentence use",
    "location_of_role": "Where the role is based",
    "hook": "A line quoted from the job description, the reason this role fits",
    "skills": "Your skills that this job asks for, as a phrase",
    "evidence": "Your most relevant project, named with its stack",
    "evidence_summary": "One line about that project",
    "evidence_link": "A link to it",
    "current_role": "Your current role as it should read in an email, from role_short",
    "current_role_full": "Your exact current job title, as on your CV",
    "availability": "When you are free to start",
    "current_company": "Where you work now",
    "current_detail": "What you do there, one clause",
    "education": "Your current qualification",
    "institution": "Where you study",
    "industry": "The company's industry, for speculative letters",
    "greeting": "Dear <name>, or a fallback greeting when no contact is known",
}


class _Forgiving(dict):
    """A missing variable renders as nothing rather than raising.

    A template is written by a person, months before the value exists. Breaking
    an entire run because one placeholder was mistyped would be the wrong trade.
    """

    def __missing__(self, key: str) -> str:
        log.dim(f"template referenced unknown variable '{key}'")
        return ""


def load(path: str | Path = DEFAULT_PATH) -> dict[str, dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warn(f"templates file is not valid JSON, ignoring it: {exc}")
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and not k.startswith("_")}


def save(templates: dict[str, Any], path: str | Path = DEFAULT_PATH) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if file_path.exists():
        try:
            existing = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing.update(templates)
    file_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


def used_variables(template: str) -> list[str]:
    return sorted(
        {name for _, name, _, _ in Formatter().parse(template or "") if name}
    )


def unknown_variables(template: str) -> list[str]:
    return [name for name in used_variables(template) if name not in VARIABLES]


def render(template: str, values: dict[str, Any], *, company: str = "", role: str = "") -> str:
    """Fill a template and put the result through the style guard."""
    if not template:
        return ""
    try:
        filled = template.format_map(_Forgiving(values))
    except (ValueError, IndexError) as exc:
        # A stray brace should not lose the message.
        log.warn(f"template could not be rendered, using it verbatim: {exc}")
        filled = template

    # Blank lines left by an empty variable read as carelessness.
    lines = [line.rstrip() for line in filled.splitlines()]
    cleaned = "\n".join(lines)
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")

    text, _ = enforce(cleaned, company=company, job_title=role, require_specifics=False)
    return text


def get(name: str, path: str | Path = DEFAULT_PATH) -> dict[str, str] | None:
    template = load(path).get(name)
    if not template:
        return None
    if not (template.get("body") or "").strip():
        return None
    return template
