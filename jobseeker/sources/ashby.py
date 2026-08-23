"""Ashby job boards: `https://api.ashbyhq.com/posting-api/job-board/{name}`."""

from __future__ import annotations

from typing import Any

from ..models import Job
from ..util import http, log
from ..util.text import strip_html
from .base import SourceError, register

API = "https://api.ashbyhq.com/posting-api/job-board/{name}"


def _to_job(board: str, raw: dict[str, Any], company_name: str) -> Job:
    location = raw.get("location", "") or ""
    compensation = raw.get("compensation") or {}
    salary = compensation.get("compensationTierSummary", "") if isinstance(compensation, dict) else ""
    return Job(
        title=raw.get("title", "").strip(),
        company_name=company_name or board.replace("-", " ").title(),
        source="ashby",
        external_id=str(raw.get("id")),
        url=raw.get("jobUrl") or raw.get("applyUrl", ""),
        location=location,
        remote=1 if raw.get("isRemote") or "remote" in location.lower() else 0,
        employment_type=raw.get("employmentType", "") or "",
        department=raw.get("department", "") or raw.get("team", "") or "",
        description=strip_html(raw.get("descriptionHtml") or raw.get("descriptionPlain", "")),
        salary=salary or "",
        posted_at=(raw.get("publishedAt") or "")[:25],
    )


@register("ashby")
def fetch(board: str = "", boards: list[str] | None = None, **_: Any) -> list[Job]:
    names = [b for b in ([board] if board else []) + list(boards or []) if b]
    if not names:
        raise SourceError("ashby source needs at least one job board name")

    jobs: list[Job] = []
    for name in names:
        try:
            payload = http.get_json(
                API.format(name=name), params={"includeCompensation": "true"}
            )
        except Exception as exc:  # noqa: BLE001
            log.warn(f"ashby board '{name}' failed: {exc}")
            continue
        company_name = payload.get("name", "") if isinstance(payload, dict) else ""
        postings = payload.get("jobs", []) if isinstance(payload, dict) else []
        for raw in postings:
            try:
                jobs.append(_to_job(name, raw, company_name))
            except Exception as exc:  # noqa: BLE001
                log.warn(f"ashby job parse failed on '{name}': {exc}")
        log.dim(f"ashby:{name} returned {len(postings)} postings")
    return jobs
