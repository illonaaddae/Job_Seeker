"""Workable job boards: the public widget API used by `apply.workable.com`."""

from __future__ import annotations

from typing import Any

from ..models import Job
from ..util import http, log
from ..util.text import strip_html
from .base import SourceError, register

API = "https://apply.workable.com/api/v1/widget/accounts/{account}"


def _to_job(account: str, raw: dict[str, Any], company_name: str) -> Job:
    location_parts = [
        raw.get("city") or "",
        raw.get("state") or "",
        raw.get("country") or "",
    ]
    location = ", ".join(p for p in location_parts if p)
    telecommuting = bool(raw.get("telecommuting"))
    return Job(
        title=(raw.get("title") or "").strip(),
        company_name=company_name or account.replace("-", " ").title(),
        source="workable",
        external_id=str(raw.get("shortcode") or raw.get("id")),
        url=raw.get("url") or raw.get("application_url", ""),
        location="Remote" if telecommuting and not location else location,
        remote=1 if telecommuting or "remote" in location.lower() else 0,
        employment_type=raw.get("employment_type", "") or "",
        department=raw.get("department", "") or "",
        description=strip_html(raw.get("description", "") + raw.get("requirements", "")),
        posted_at=(raw.get("published_on") or raw.get("created_at") or "")[:25],
    )


@register("workable")
def fetch(account: str = "", accounts: list[str] | None = None, **_: Any) -> list[Job]:
    handles = [a for a in ([account] if account else []) + list(accounts or []) if a]
    if not handles:
        raise SourceError("workable source needs at least one account subdomain")

    jobs: list[Job] = []
    for handle in handles:
        try:
            payload = http.get_json(API.format(account=handle), params={"details": "true"})
        except Exception as exc:  # noqa: BLE001
            log.warn(f"workable account '{handle}' failed: {exc}")
            continue
        company_name = payload.get("name", "") if isinstance(payload, dict) else ""
        postings = payload.get("jobs", []) if isinstance(payload, dict) else []
        for raw in postings:
            try:
                jobs.append(_to_job(handle, raw, company_name))
            except Exception as exc:  # noqa: BLE001
                log.warn(f"workable job parse failed on '{handle}': {exc}")
        log.dim(f"workable:{handle} returned {len(postings)} postings")
    return jobs
