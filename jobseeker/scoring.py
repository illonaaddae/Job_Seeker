"""Explainable job matching.

Every job gets a 0 to 100 score built from named signals, and the breakdown is
stored alongside it. The point is that a low score can always be explained in
one line, so the dashboard can say *why* something was skipped instead of
showing an opaque number.

Upstream had no scoring at all: it emailed every company it found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .persona import Persona
from .util.text import contains_phrase, normalize, token_set

# Weight ceiling per signal. They sum to 100.
WEIGHTS = {
    "title": 26,
    "skills": 30,
    "seniority": 18,
    "location": 14,
    "freshness": 6,
    "signal": 6,
}

MAX_SCORED_CHARS = 9000

_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:to\s*\d{1,2}\s*)?year", re.I)
_REMOTE_RE = re.compile(r"\b(remote|work from home|distributed|anywhere|hybrid)\b", re.I)
_ONSITE_ONLY_RE = re.compile(r"\b(on[- ]site only|in[- ]office (?:only|required)|no remote)\b", re.I)


@dataclass(slots=True)
class ScoreResult:
    score: float
    signals: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    required_years: int | None = None

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "signals": self.signals,
            "reasons": self.reasons,
            "blockers": self.blockers,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "required_years": self.required_years,
        }

    def explain(self) -> str:
        if self.blocked:
            return f"blocked: {self.blockers[0]}"
        top = sorted(self.signals.items(), key=lambda kv: kv[1], reverse=True)[:3]
        return ", ".join(f"{name} {value:.0f}" for name, value in top)


def _title_signal(persona: Persona, title: str) -> tuple[float, str]:
    """How closely the posted title matches a role the applicant actually wants."""
    roles = persona.targeting.get("roles", [])
    normalised_title = normalize(title)
    if not normalised_title:
        return 0.0, "no title"

    for role in roles:
        if normalize(role) == normalised_title:
            return 1.0, f"exact title match on '{role}'"
    for role in roles:
        if contains_phrase(title, role):
            return 0.9, f"title contains '{role}'"

    title_tokens = token_set(title)
    best_ratio, best_role = 0.0, ""
    for role in roles:
        role_tokens = token_set(role)
        if not role_tokens:
            continue
        ratio = len(title_tokens & role_tokens) / len(role_tokens)
        if ratio > best_ratio:
            best_ratio, best_role = ratio, role
    if best_ratio >= 0.5:
        return 0.55 + best_ratio * 0.3, f"title overlaps '{best_role}'"
    if best_ratio > 0:
        return best_ratio * 0.5, f"weak title overlap with '{best_role}'"
    return 0.0, "title is outside the target roles"


def _skills_signal(persona: Persona, text: str) -> tuple[float, list[str], list[str], str]:
    """Weighted share of the applicant's skill capital that this job asks for."""
    matched = persona.matched_skills(text)
    if not matched:
        return 0.0, [], [], "job names none of the profile skills"

    core_total = sum(s.weight for s in persona.skills if s.tier == "core")
    matched_core = sum(s.weight for s in matched if s.tier == "core")
    matched_secondary = sum(s.weight for s in matched if s.tier == "secondary")

    # Core coverage dominates; secondary skills top it up but cannot carry a job
    # that needs none of the core stack.
    core_ratio = matched_core / core_total if core_total else 0.0
    secondary_bonus = min(matched_secondary / 40.0, 0.35)
    raw = min(core_ratio * 1.35 + secondary_bonus, 1.0)

    matched_names = [s.name for s in matched]
    missing = persona.missing_requirements(text, COMMON_TECH_VOCABULARY)
    reason = f"matches {len(matched_names)} profile skills including {', '.join(matched_names[:4])}"
    return raw, matched_names, missing[:8], reason


def _stack_mismatch(persona: Persona, title: str) -> str:
    """Block roles whose title is built around a stack the applicant does not use.

    A title is the employer's own summary of the job. If it leads with a
    language that is nowhere in the profile, no amount of description overlap
    makes it a real match, and applying anyway is how an automated system
    starts sending noise.
    """
    foreign = persona.targeting.get("foreign_stacks", [])
    for stack in foreign:
        if contains_phrase(title, stack):
            owns = any(
                contains_phrase(title, form)
                for skill in persona.skills
                if skill.tier == "core"
                for form in skill.surface_forms
            )
            if not owns:
                return f"title is built around {stack}, which is not on the profile"
    return ""


def _seniority_signal(persona: Persona, title: str, text: str) -> tuple[float, str, int | None]:
    """Reject roles pitched above the applicant's level, reward ones pitched at it."""
    targeting = persona.targeting
    haystack = f"{title} {text[:2500]}"

    for term in targeting.get("seniority_exclude", []):
        if contains_phrase(title, term):
            return 0.0, f"title is {term} level", None

    # A posting often names several figures ("2+ years of React, 6+ years total").
    # The lowest is the entry bar, but the highest still says how senior the role
    # really is, so both are kept and both affect the score.
    mentioned = [
        int(match.group(1)) for match in _YEARS_RE.finditer(text) if 0 < int(match.group(1)) <= 25
    ]
    years_required = min(mentioned) if mentioned else None
    years_ceiling = max(mentioned) if mentioned else None

    score = 0.6
    reason = "no explicit seniority signal"
    for term in targeting.get("seniority", []):
        if contains_phrase(title, term):
            score, reason = 1.0, f"title is {term} level"
            break
    else:
        if contains_phrase(haystack, "graduate") or contains_phrase(haystack, "entry level"):
            score, reason = 0.9, "described as entry level"

    if years_ceiling is not None and years_ceiling >= 6:
        # Something in this posting wants far more experience than she has, even
        # if the headline requirement looks reachable.
        score = min(score, 0.55)
        reason = f"a requirement of {years_ceiling}+ years appears in this posting"

    if years_required is not None:
        if years_required <= 2:
            score = max(score, 0.85) if (years_ceiling or 0) < 6 else score
            reason = (
                f"asks for {years_required}+ years, which is reachable"
                if (years_ceiling or 0) < 6
                else reason
            )
        elif years_required <= 4:
            score = min(score, 0.5)
            reason = f"asks for {years_required}+ years, a stretch"
        else:
            score = min(score, 0.12)
            reason = f"asks for {years_required}+ years, well beyond current experience"

    return score, reason, years_required


def _location_signal(persona: Persona, job_location: str, remote_flag: int, text: str) -> tuple[float, str]:
    targeting = persona.targeting
    location_text = f"{job_location} {text[:1500]}"

    if _ONSITE_ONLY_RE.search(location_text) and not _matches_onsite_country(persona, job_location):
        return 0.0, "on site only in a country that does not work"

    if remote_flag or _REMOTE_RE.search(location_text):
        if contains_phrase(location_text, "hybrid") and not _matches_onsite_country(persona, job_location):
            return 0.35, "hybrid, which needs relocation"
        return 1.0, "remote friendly"

    for wanted in targeting.get("locations", []):
        if contains_phrase(location_text, wanted):
            return 0.95, f"location matches '{wanted}'"

    if _matches_onsite_country(persona, job_location):
        return 0.9, "on site in a country that works"

    if not job_location:
        return 0.5, "location not stated"

    return 0.15, f"location '{job_location}' needs relocation"


def _matches_onsite_country(persona: Persona, location: str) -> bool:
    return any(
        contains_phrase(location, country)
        for country in persona.targeting.get("onsite_countries", [])
    )


def _freshness_signal(posted_at: str) -> tuple[float, str]:
    """A posting that has been open for months is usually already filled."""
    if not posted_at:
        return 0.6, "posting date unknown"
    try:
        cleaned = posted_at.replace("Z", "+00:00")
        posted = datetime.fromisoformat(cleaned)
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.6, "posting date unparseable"
    age_days = (datetime.now(timezone.utc) - posted).days
    if age_days <= 3:
        return 1.0, f"posted {age_days} day(s) ago"
    if age_days <= 14:
        return 0.85, f"posted {age_days} days ago"
    if age_days <= 30:
        return 0.6, f"posted {age_days} days ago"
    if age_days <= 60:
        return 0.3, f"posted {age_days} days ago"
    return 0.1, f"stale, posted {age_days} days ago"


def _signal_quality(text: str) -> tuple[float, str]:
    """Thin descriptions cannot be tailored against, so they are worth less."""
    words = len(text.split())
    if words < 60:
        return 0.2, "description too thin to tailor against"
    if words < 200:
        return 0.6, "short description"
    return 1.0, "full description available"


COMMON_TECH_VOCABULARY = (
    "React", "Angular", "Vue", "Svelte", "Next.js", "Nuxt", "TypeScript", "JavaScript",
    "Python", "Java", "Kotlin", "Swift", "Go", "Rust", "Ruby", "PHP", "C#", ".NET",
    "Node.js", "Django", "Flask", "FastAPI", "Spring", "Rails", "Laravel",
    "GraphQL", "REST", "gRPC", "PostgreSQL", "MySQL", "MongoDB", "Redis", "DynamoDB",
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "CI/CD", "Jenkins",
    "Tailwind", "SCSS", "Figma", "Redux", "React Native", "Flutter", "Electron",
    "TensorFlow", "PyTorch", "scikit-learn", "Pandas", "Spark", "Kafka", "Elasticsearch",
    "Jest", "Cypress", "Playwright", "Vitest", "Storybook", "Webpack", "Vite",
)


def score_job(
    persona: Persona,
    *,
    title: str,
    description: str,
    location: str = "",
    remote: int = 0,
    posted_at: str = "",
    company_name: str = "",
) -> ScoreResult:
    """Score one job against the profile and explain every point awarded."""
    # Past a few thousand words a posting is benefits and legal boilerplate,
    # which costs time to scan and adds no matching signal.
    description = description[:MAX_SCORED_CHARS]
    text = f"{title}\n{description}"
    normalised_text = normalize(text)
    result = ScoreResult(score=0.0)

    # Hard exclusions run first. A blocked job scores zero no matter how well it
    # would otherwise match, and the blocker is recorded for the dashboard.
    for phrase in persona.targeting.get("exclude_keywords", []):
        if contains_phrase(normalised_text, phrase, normalised=True):
            result.blockers.append(f"excluded keyword '{phrase}'")

    mismatch = _stack_mismatch(persona, title)
    if mismatch:
        result.blockers.append(mismatch)

    title_raw, title_reason = _title_signal(persona, title)
    skills_raw, matched, missing, skills_reason = _skills_signal(persona, description or title)
    seniority_raw, seniority_reason, years = _seniority_signal(persona, title, description)
    location_raw, location_reason = _location_signal(persona, location, remote, description)
    freshness_raw, freshness_reason = _freshness_signal(posted_at)
    quality_raw, quality_reason = _signal_quality(description)

    if seniority_raw == 0.0:
        result.blockers.append(seniority_reason)
    if location_raw == 0.0:
        result.blockers.append(location_reason)
    if title_raw == 0.0:
        result.blockers.append(title_reason)

    result.signals = {
        "title": round(title_raw * WEIGHTS["title"], 2),
        "skills": round(skills_raw * WEIGHTS["skills"], 2),
        "seniority": round(seniority_raw * WEIGHTS["seniority"], 2),
        "location": round(location_raw * WEIGHTS["location"], 2),
        "freshness": round(freshness_raw * WEIGHTS["freshness"], 2),
        "signal": round(quality_raw * WEIGHTS["signal"], 2),
    }
    result.reasons = [
        title_reason, skills_reason, seniority_reason,
        location_reason, freshness_reason, quality_reason,
    ]
    result.matched_skills = matched
    result.missing_skills = missing
    result.required_years = years
    result.score = 0.0 if result.blocked else round(sum(result.signals.values()), 2)
    return result
