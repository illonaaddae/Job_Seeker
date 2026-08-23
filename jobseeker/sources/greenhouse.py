"""Greenhouse job boards.

Public, unauthenticated, and the full job description comes back in one call:
`https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`
"""

from __future__ import annotations

from typing import Any

from ..models import Job
from ..util import http, log
from ..util.text import strip_html
from .base import SourceError, register

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def _to_job(board_token: str, raw: dict[str, Any]) -> Job:
    location = (raw.get("location") or {}).get("name", "")
    content = strip_html(raw.get("content", ""))
    metadata = {m.get("name"): m.get("value") for m in raw.get("metadata") or []}
    department = ""
    if raw.get("departments"):
        department = raw["departments"][0].get("name", "")
    return Job(
        title=raw.get("title", "").strip(),
        company_name=raw.get("company_name") or board_token.replace("-", " ").title(),
        source="greenhouse",
        external_id=str(raw.get("id")),
        url=raw.get("absolute_url", ""),
        location=location,
        remote=1 if "remote" in location.lower() else 0,
        department=department,
        description=content,
        employment_type=str(metadata.get("Employment Type") or ""),
        posted_at=(raw.get("first_published") or raw.get("updated_at") or "")[:25],
    )


@register("greenhouse")
def fetch(board: str = "", boards: list[str] | None = None, **_: Any) -> list[Job]:
    """Pull every open posting from one or more Greenhouse boards."""
    tokens = [t for t in ([board] if board else []) + list(boards or []) if t]
    if not tokens:
        raise SourceError("greenhouse source needs at least one board token")

    jobs: list[Job] = []
    for token in tokens:
        try:
            payload = http.get_json(API.format(token=token), params={"content": "true"})
        except Exception as exc:  # noqa: BLE001 - one bad board must not stop the run
            log.warn(f"greenhouse board '{token}' failed: {exc}")
            continue
        board_jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        for raw in board_jobs:
            try:
                jobs.append(_to_job(token, raw))
            except Exception as exc:  # noqa: BLE001
                log.warn(f"greenhouse job parse failed on board '{token}': {exc}")
        log.dim(f"greenhouse:{token} returned {len(board_jobs)} postings")
    return jobs
