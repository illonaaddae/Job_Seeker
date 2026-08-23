"""Keyless aggregator feeds.

Arbeitnow and RemoteOK both publish free, unauthenticated job feeds with real
descriptions. They give the engine volume on day one, before any paid API key
exists, which matters when the whole point is applying at scale.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import Job
from ..util import http, log
from ..util.text import contains_phrase, strip_html
from .base import register

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
REMOTEOK_API = "https://remoteok.com/api"


def _keyword_filter(job: Job, keywords: list[str] | None) -> bool:
    if not keywords:
        return True
    haystack = f"{job.title} {job.description[:1200]}"
    return any(contains_phrase(haystack, k) for k in keywords)


@register("arbeitnow")
def fetch_arbeitnow(
    keywords: list[str] | None = None, pages: int = 2, **_: Any
) -> list[Job]:
    """Arbeitnow aggregates European and remote roles. No key, no rate limit tricks."""
    jobs: list[Job] = []
    for page in range(1, max(1, pages) + 1):
        try:
            payload = http.get_json(ARBEITNOW_API, params={"page": page})
        except Exception as exc:  # noqa: BLE001
            log.warn(f"arbeitnow page {page} failed: {exc}")
            break
        entries = payload.get("data", []) if isinstance(payload, dict) else []
        if not entries:
            break
        for raw in entries:
            created = raw.get("created_at")
            posted = ""
            if isinstance(created, (int, float)):
                posted = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
            job = Job(
                title=(raw.get("title") or "").strip(),
                company_name=(raw.get("company_name") or "").strip(),
                source="arbeitnow",
                external_id=str(raw.get("slug") or raw.get("url", "")),
                url=raw.get("url", ""),
                location=raw.get("location", "") or "",
                remote=1 if raw.get("remote") else 0,
                employment_type=", ".join(raw.get("job_types") or []),
                description=strip_html(raw.get("description", "")),
                posted_at=posted,
            )
            if job.title and _keyword_filter(job, keywords):
                jobs.append(job)
        log.dim(f"arbeitnow page {page} returned {len(entries)} postings")
    return jobs


@register("remoteok")
def fetch_remoteok(keywords: list[str] | None = None, **_: Any) -> list[Job]:
    """RemoteOK is remote only, which fits a Ghana based applicant well."""
    try:
        payload = http.get_json(REMOTEOK_API)
    except Exception as exc:  # noqa: BLE001
        log.warn(f"remoteok failed: {exc}")
        return []
    entries = payload if isinstance(payload, list) else []
    jobs: list[Job] = []
    for raw in entries:
        # The first element of the feed is a legal notice, not a job.
        if not isinstance(raw, dict) or not raw.get("position"):
            continue
        salary_min, salary_max = raw.get("salary_min"), raw.get("salary_max")
        salary = (
            f"${int(salary_min):,} to ${int(salary_max):,}"
            if salary_min and salary_max
            else ""
        )
        job = Job(
            title=str(raw.get("position", "")).strip(),
            company_name=str(raw.get("company", "")).strip(),
            source="remoteok",
            external_id=str(raw.get("id") or raw.get("slug", "")),
            url=raw.get("url", "") or raw.get("apply_url", ""),
            location=raw.get("location", "") or "Remote",
            remote=1,
            description=strip_html(raw.get("description", "")),
            salary=salary,
            posted_at=(raw.get("date") or "")[:25],
        )
        if job.title and _keyword_filter(job, keywords):
            jobs.append(job)
    log.dim(f"remoteok returned {len(jobs)} matching postings")
    return jobs
