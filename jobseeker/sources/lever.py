"""Lever job boards: `https://api.lever.co/v0/postings/{company}?mode=json`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import Job
from ..util import http, log
from ..util.text import strip_html
from .base import SourceError, register

API = "https://api.lever.co/v0/postings/{company}"


def _to_job(company: str, raw: dict[str, Any]) -> Job:
    categories = raw.get("categories") or {}
    location = categories.get("location", "") or ""
    workplace = (raw.get("workplaceType") or "").lower()
    description = strip_html(raw.get("descriptionPlain") or raw.get("description", ""))
    for section in raw.get("lists") or []:
        description += "\n\n" + section.get("text", "") + "\n" + strip_html(section.get("content", ""))
    posted = ""
    if raw.get("createdAt"):
        posted = datetime.fromtimestamp(raw["createdAt"] / 1000, tz=timezone.utc).isoformat()
    return Job(
        title=raw.get("text", "").strip(),
        company_name=company.replace("-", " ").title(),
        source="lever",
        external_id=str(raw.get("id")),
        url=raw.get("hostedUrl", ""),
        location=location,
        remote=1 if workplace == "remote" or "remote" in location.lower() else 0,
        employment_type=categories.get("commitment", "") or "",
        department=categories.get("team", "") or "",
        description=description.strip(),
        posted_at=posted,
    )


@register("lever")
def fetch(company: str = "", companies: list[str] | None = None, **_: Any) -> list[Job]:
    handles = [c for c in ([company] if company else []) + list(companies or []) if c]
    if not handles:
        raise SourceError("lever source needs at least one company handle")

    jobs: list[Job] = []
    for handle in handles:
        try:
            payload = http.get_json(API.format(company=handle), params={"mode": "json"})
        except Exception as exc:  # noqa: BLE001
            log.warn(f"lever board '{handle}' failed: {exc}")
            continue
        postings = payload if isinstance(payload, list) else []
        for raw in postings:
            try:
                jobs.append(_to_job(handle, raw))
            except Exception as exc:  # noqa: BLE001
                log.warn(f"lever job parse failed on '{handle}': {exc}")
        log.dim(f"lever:{handle} returned {len(postings)} postings")
    return jobs
