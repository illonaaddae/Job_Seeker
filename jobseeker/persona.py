"""The applicant, as structured data.

Every generator reads from here, so switching the profile JSON switches whose
applications the engine writes. Nothing about Illona is hardcoded in code paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .util.text import contains_phrase, normalize, token_set


@dataclass(slots=True)
class Skill:
    name: str
    aliases: list[str]
    weight: int
    tier: str
    evidence: str = ""

    @property
    def surface_forms(self) -> list[str]:
        return [self.name, *self.aliases]

    def mentioned_in(self, text: str, *, normalised: bool = False) -> bool:
        return any(
            contains_phrase(text, form, normalised=normalised) for form in self.surface_forms
        )


class Persona:
    """Read-only view over a profile JSON document."""

    def __init__(self, data: dict[str, Any], source_path: Path | None = None) -> None:
        self.data = data
        self.source_path = source_path
        self._skills: list[Skill] | None = None

    # ------------------------------------------------------------------ load

    @classmethod
    def load(cls, path: str | Path) -> "Persona":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(
                f"Profile not found at {p}. Copy data/profile.example.json and edit it, "
                f"or point PROFILE_PATH at your own file."
            )
        data = json.loads(p.read_text(encoding="utf-8"))
        missing = [k for k in ("identity", "targeting", "skills") if k not in data]
        if missing:
            raise ValueError(f"Profile {p} is missing required sections: {', '.join(missing)}")
        return cls(data, p)

    # ------------------------------------------------------------- accessors

    @property
    def identity(self) -> dict[str, Any]:
        return self.data.get("identity", {})

    @property
    def targeting(self) -> dict[str, Any]:
        return self.data.get("targeting", {})

    @property
    def narrative(self) -> dict[str, Any]:
        return self.data.get("narrative", {})

    @property
    def outreach(self) -> dict[str, Any]:
        return self.data.get("outreach", {})

    @property
    def projects(self) -> list[dict[str, Any]]:
        return self.data.get("projects", [])

    @property
    def experience(self) -> list[dict[str, Any]]:
        return self.data.get("experience", [])

    @property
    def education(self) -> list[dict[str, Any]]:
        return self.data.get("education", [])

    @property
    def certifications(self) -> list[dict[str, Any]]:
        return self.data.get("certifications", [])

    @property
    def name(self) -> str:
        return self.identity.get("full_name", "Applicant")

    @property
    def first_name(self) -> str:
        return self.name.split()[0]

    @property
    def email(self) -> str:
        return self.identity.get("email", "")

    @property
    def cv_path(self) -> str:
        return self.data.get("documents", {}).get("cv_path", "")

    @property
    def skills(self) -> list[Skill]:
        if self._skills is None:
            skills: list[Skill] = []
            for tier in ("core", "secondary", "learning"):
                for entry in self.data.get("skills", {}).get(tier, []):
                    skills.append(
                        Skill(
                            name=entry["name"],
                            aliases=entry.get("aliases", []),
                            weight=int(entry.get("weight", 1)),
                            tier=tier,
                            evidence=entry.get("evidence", ""),
                        )
                    )
            self._skills = skills
        return self._skills

    def skill_names(self, tiers: Iterable[str] = ("core", "secondary")) -> list[str]:
        wanted = set(tiers)
        return [s.name for s in self.skills if s.tier in wanted]

    # -------------------------------------------------------------- matching

    def matched_skills(self, text: str) -> list[Skill]:
        """Skills the applicant actually has that this job description asks for."""
        haystack = normalize(text)
        return [s for s in self.skills if s.mentioned_in(haystack, normalised=True)]

    def missing_requirements(self, text: str, vocabulary: Iterable[str]) -> list[str]:
        """Technologies named in the job that the profile cannot back up."""
        owned = {normalize(form) for s in self.skills for form in s.surface_forms}
        haystack = normalize(text)
        found = []
        for term in vocabulary:
            if normalize(term) in owned:
                continue
            if contains_phrase(haystack, term, normalised=True):
                found.append(term)
        return found

    def project_for(self, evidence_id: str) -> dict[str, Any] | None:
        for project in self.projects:
            if project.get("id") == evidence_id:
                return project
        return None

    def best_evidence(self, job_text: str, limit: int = 2) -> list[dict[str, Any]]:
        """Rank the applicant's own projects by overlap with this job description.

        This is what stops letters being generic: the letter cites the project
        that actually shares vocabulary with the posting, not a fixed favourite.

        Projects are listed strongest first, and that ordering carries weight.
        Without it, a side project with a keyword rich description outranks
        substantial professional work that happens to be described plainly.
        """
        job_tokens = token_set(job_text)
        ranked: list[tuple[float, dict[str, Any]]] = []
        for index, project in enumerate(self.projects):
            haystack = " ".join(
                [
                    project.get("name", ""),
                    project.get("summary", ""),
                    " ".join(project.get("stack", [])),
                    " ".join(project.get("keywords", [])),
                    " ".join(project.get("highlights", [])),
                ]
            )
            overlap = job_tokens & token_set(haystack)
            keyword_hits = sum(
                2.0 for k in project.get("keywords", []) if contains_phrase(job_text, k)
            )
            stack_hits = sum(1.5 for k in project.get("stack", []) if contains_phrase(job_text, k))
            position_weight = max(0.0, 5.0 - index * 1.6)
            score = len(overlap) * 0.5 + keyword_hits + stack_hits + position_weight
            ranked.append((score, project))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [project for score, project in ranked[:limit] if score > 0] or self.projects[:1]

    def best_experience(self, job_text: str, limit: int = 2) -> list[dict[str, Any]]:
        """Rank roles by relevance, with seniority of position respected.

        Keyword overlap alone puts old or peripheral work first whenever a job
        advert happens to share its vocabulary: a "Web Developer" posting would
        surface freelance WordPress ahead of current engineering work. The
        profile lists experience strongest first, so that order carries weight
        which relevance has to beat rather than ignore.
        """
        haystack = normalize(job_text)
        job_tokens = token_set(job_text)
        ranked: list[tuple[float, dict[str, Any]]] = []

        for index, role in enumerate(self.experience):
            hits = sum(
                2.0
                for k in role.get("keywords", [])
                if contains_phrase(haystack, k, normalised=True)
            )
            overlap = job_tokens & token_set(" ".join(role.get("bullets", [])))
            position_weight = max(0.0, 4.0 - index * 1.5)
            ranked.append((hits + len(overlap) * 0.3 + position_weight, role))

        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [role for _, role in ranked[:limit]]

    # ---------------------------------------------------------------- output

    def signature(self) -> str:
        lines = self.outreach.get("signature_lines")
        if lines:
            return "\n".join(lines)
        identity = self.identity
        return "\n".join(
            filter(
                None,
                [
                    identity.get("full_name", ""),
                    identity.get("headline", ""),
                    identity.get("website", ""),
                    identity.get("phone", ""),
                ],
            )
        )

    def prompt_context(self, job_text: str = "") -> str:
        """A compact, high signal profile briefing for an LLM.

        Only the evidence relevant to this job is included, which keeps the
        prompt small and pushes the model towards specifics rather than a
        rewrite of the whole CV.
        """
        identity = self.identity
        narrative = self.narrative
        projects = self.best_evidence(job_text, limit=3) if job_text else self.projects[:3]
        roles = self.best_experience(job_text, limit=3) if job_text else self.experience[:3]

        parts: list[str] = []
        parts.append(
            f"APPLICANT: {identity.get('full_name')} ({identity.get('pronouns', 'she/her')}), "
            f"{identity.get('headline')}, based in {identity.get('location')}."
        )
        parts.append(
            f"CONTACT: {identity.get('email')} | {identity.get('website')} | "
            f"{identity.get('github')} | {identity.get('linkedin')}"
        )
        if narrative.get("summary"):
            parts.append(f"SUMMARY: {narrative['summary']}")
        if narrative.get("positioning"):
            parts.append(f"POSITIONING: {narrative['positioning']}")

        parts.append("CORE SKILLS: " + ", ".join(self.skill_names(("core",))))
        parts.append("WORKING SKILLS: " + ", ".join(self.skill_names(("secondary",))))

        parts.append("RELEVANT EXPERIENCE:")
        for role in roles:
            parts.append(
                f"- {role.get('role')} at {role.get('company')} ({role.get('period')}): "
                + " ".join(role.get("bullets", [])[:2])
            )

        parts.append("RELEVANT PROJECTS:")
        for project in projects:
            stack = ", ".join(project.get("stack", [])[:6])
            link = project.get("url") or project.get("repo") or ""
            parts.append(
                f"- {project.get('name')} [{stack}] {link}: {project.get('summary')} "
                + (project.get("highlights", [""])[0] if project.get("highlights") else "")
            )

        if self.education:
            parts.append(
                "EDUCATION: "
                + "; ".join(
                    f"{e.get('credential')}, {e.get('institution')} ({e.get('period')})"
                    for e in self.education
                )
            )
        if self.certifications:
            parts.append(
                "CERTIFICATIONS: "
                + "; ".join(f"{c.get('name')} ({c.get('issuer')})" for c in self.certifications)
            )
        if narrative.get("differentiators"):
            parts.append("WHAT SETS HER APART:")
            parts.extend(f"- {d}" for d in narrative["differentiators"])
        if self.outreach.get("never_claim"):
            parts.append(
                "MUST NEVER CLAIM: " + "; ".join(self.outreach["never_claim"]) + "."
            )
        return "\n".join(parts)
