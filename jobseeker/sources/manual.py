"""Manual ingestion: one job URL, or a CSV of them.

Used when a role arrives through LinkedIn, a referral, or a WhatsApp group.
The page is fetched, reduced to text, and treated exactly like an API sourced
job so it flows through the same scoring and drafting path.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..models import Job
from ..util import http, log
from ..util.text import strip_html, truncate
from .base import SourceError, register

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_OG_TITLE_RE = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', re.I)
_OG_SITE_RE = re.compile(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\'](.*?)["\']', re.I)


def _guess_company(html: str, url: str) -> str:
    match = _OG_SITE_RE.search(html)
    if match:
        return match.group(1).strip()
    host = urlparse(url).netloc.replace("www.", "")
    root = host.split(".")[0]
    return root.replace("-", " ").title()


def _guess_title(html: str) -> str:
    match = _OG_TITLE_RE.search(html) or _TITLE_RE.search(html)
    if not match:
        return "Untitled role"
    title = strip_html(match.group(1)).strip()
    # Page titles are usually "Role at Company | Board" — keep the role half.
    for separator in (" at ", " | ", " - ", " · "):
        if separator in title:
            title = title.split(separator)[0].strip()
            break
    return title or "Untitled role"


@register("url")
def fetch_url(url: str = "", company: str = "", title: str = "", **_: Any) -> list[Job]:
    """Turn a single job posting URL into a scoreable job."""
    if not url:
        raise SourceError("url source needs a job posting URL")
    try:
        html = http.get_text(url, timeout=25)
    except Exception as exc:  # noqa: BLE001
        raise SourceError(f"could not fetch {url}: {exc}") from exc

    description = strip_html(html)
    if len(description) < 120:
        log.warn(
            "The page returned almost no text. It is probably rendered by JavaScript. "
            "Paste the description manually with: jobseeker add-job --description-file <path>"
        )
    return [
        Job(
            title=title or _guess_title(html),
            company_name=company or _guess_company(html, url),
            source="url",
            external_id=url,
            url=url,
            description=truncate(description, 20000, suffix=""),
            location="",
        )
    ]


@register("csv")
def fetch_csv(path: str = "", **_: Any) -> list[Job]:
    """Import a CSV with at least `title` and `company_name` columns."""
    file_path = Path(path)
    if not file_path.exists():
        raise SourceError(f"CSV not found: {file_path}")
    jobs: list[Job] = []
    with file_path.open(encoding="utf-8", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            title = (row.get("title") or "").strip()
            company = (row.get("company_name") or row.get("company") or "").strip()
            if not title or not company:
                log.warn(f"row {index + 2} skipped: title and company_name are required")
                continue
            jobs.append(
                Job(
                    title=title,
                    company_name=company,
                    source="csv",
                    external_id=row.get("url") or f"{company}:{title}",
                    url=(row.get("url") or "").strip(),
                    location=(row.get("location") or "").strip(),
                    remote=1 if (row.get("remote") or "").strip().lower() in {"1", "yes", "true"} else 0,
                    description=(row.get("description") or "").strip(),
                    posted_at=(row.get("posted_at") or "").strip(),
                )
            )
    log.dim(f"csv import read {len(jobs)} rows from {file_path}")
    return jobs
