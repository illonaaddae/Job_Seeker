"""Resolve a company domain into someone worth writing to.

Order of preference, cheapest and most reliable first:

1. Hunter.io domain search, which returns named people with roles and a
   confidence score.
2. Prospeo domain search as a second opinion when Hunter has nothing.
3. Apify contact scraper over the company's own site, which finds the generic
   inbox when no personal address is public.

Generic inboxes are kept but ranked last, and role based addresses that are
clearly wrong for a job application (invoices, support, privacy) are dropped
entirely rather than emailed.
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlparse

from ..models import Contact
from ..util import env, http, log

HUNTER_API = "https://api.hunter.io/v2/domain-search"
PROSPEO_API = "https://api.prospeo.io/domain-search"
APIFY_ACTOR = "https://api.apify.com/v2/acts/vdrmota~contact-info-scraper/runs"

# Roles worth writing to about a job, best first.
PREFERRED_ROLES = (
    "talent", "recruit", "people", "hr", "hiring", "engineering manager",
    "head of engineering", "cto", "vp engineering", "founder", "careers",
)
PREFERRED_LOCAL_PARTS = ("careers", "jobs", "recruitment", "talent", "hr", "people", "hello", "info", "contact")
# Never write to these, no matter what a scraper returns.
BLOCKED_LOCAL_PARTS = (
    "noreply", "no-reply", "donotreply", "postmaster", "abuse", "privacy", "legal",
    "invoice", "billing", "accounts", "payments", "security", "unsubscribe", "dmarc",
    "webmaster", "admin", "support", "helpdesk", "sales",
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def normalise_domain(value: str) -> str:
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"
    return urlparse(value).netloc.removeprefix("www.").lower()


def _local_part(email: str) -> str:
    return email.split("@", 1)[0].lower()


def _is_sendable(email: str) -> bool:
    if not _EMAIL_RE.fullmatch(email or ""):
        return False
    local = _local_part(email)
    return not any(blocked in local for blocked in BLOCKED_LOCAL_PARTS)


def _role_score(title: str, email: str) -> int:
    """Higher is better. Named humans in hiring roles win."""
    title_l = (title or "").lower()
    score = 0
    for index, role in enumerate(PREFERRED_ROLES):
        if role in title_l:
            score += 60 - index * 3
            break
    local = _local_part(email)
    if local in PREFERRED_LOCAL_PARTS:
        score += 25
    if "." in local and local not in PREFERRED_LOCAL_PARTS:
        score += 15  # firstname.lastname is a real person
    return score


def _from_hunter(domain: str, limit: int) -> list[dict[str, Any]]:
    api_key = env.get("HUNTER_API_KEY")
    if not api_key:
        return []
    try:
        data = http.get_json(
            HUNTER_API, params={"domain": domain, "api_key": api_key, "limit": limit}
        )
    except Exception as exc:  # noqa: BLE001
        log.warn(f"hunter lookup failed for {domain}: {exc}")
        return []
    results = []
    for entry in (data.get("data", {}) or {}).get("emails", []):
        email = entry.get("value", "")
        if not _is_sendable(email):
            continue
        results.append(
            {
                "email": email,
                "name": " ".join(
                    p for p in [entry.get("first_name"), entry.get("last_name")] if p
                ),
                "title": entry.get("position") or entry.get("department") or "",
                "linkedin": entry.get("linkedin") or "",
                "confidence": int(entry.get("confidence") or 0),
                "source": "hunter",
                "verified": 1 if entry.get("verification", {}).get("status") == "valid" else 0,
            }
        )
    return results


def _from_prospeo(domain: str, limit: int) -> list[dict[str, Any]]:
    api_key = env.get("PROSPEO_API_KEY")
    if not api_key:
        return []
    try:
        data = http.post_json(
            PROSPEO_API,
            json_body={"company": domain, "limit": limit},
            headers={"X-KEY": api_key},
        )
    except Exception as exc:  # noqa: BLE001
        log.warn(f"prospeo lookup failed for {domain}: {exc}")
        return []
    response = data.get("response", {}) if isinstance(data, dict) else {}
    results = []
    for entry in response.get("email_list", []) or []:
        email = entry.get("email", "")
        if not _is_sendable(email):
            continue
        results.append(
            {
                "email": email,
                "name": entry.get("full_name", "") or "",
                "title": entry.get("job_title", "") or "",
                "linkedin": entry.get("linkedin_url", "") or "",
                "confidence": 70,
                "source": "prospeo",
                "verified": 0,
            }
        )
    return results


def _from_apify(website: str, max_pages: int = 8) -> list[dict[str, Any]]:
    token = env.get("APIFY_API_TOKEN")
    if not token or not website:
        return []
    payload = {
        "startUrls": [{"url": website}],
        "maxRequestsPerStartUrl": max_pages,
        "maxDepth": 1,
        "proxyConfiguration": {"useApifyProxy": True},
    }
    try:
        run = http.post_json(f"{APIFY_ACTOR}?token={token}", json_body=payload, timeout=45)
    except Exception as exc:  # noqa: BLE001
        log.warn(f"apify run failed for {website}: {exc}")
        return []

    run_data = run.get("data", {}) if isinstance(run, dict) else {}
    run_id, dataset_id = run_data.get("id"), run_data.get("defaultDatasetId")
    if not run_id or not dataset_id:
        return []

    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}"
    for _ in range(30):
        time.sleep(8)
        try:
            status = http.get_json(status_url).get("data", {}).get("status")
        except Exception:  # noqa: BLE001
            break
        if status in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
            if status != "SUCCEEDED":
                log.warn(f"apify run for {website} ended as {status}")
            break

    try:
        items = http.get_json(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={token}"
        )
    except Exception as exc:  # noqa: BLE001
        log.warn(f"apify dataset fetch failed: {exc}")
        return []

    results = []
    for item in items if isinstance(items, list) else []:
        for email in item.get("emails", []) or []:
            if _is_sendable(email):
                results.append(
                    {
                        "email": email,
                        "name": "",
                        "title": "",
                        "linkedin": "",
                        "confidence": 35,
                        "source": "apify",
                        "verified": 0,
                    }
                )
    return results


def find_contacts(
    company_id: int,
    *,
    domain: str = "",
    website: str = "",
    limit: int = 5,
    use_scraper: bool = True,
) -> list[Contact]:
    """Return ranked, sendable contacts for one company."""
    domain = normalise_domain(domain or website)
    if not domain:
        return []

    log.info(f"Finding contacts at {domain}")

    # The company's own site is free and often enough, so it is tried first.
    # The paid services are a fallback, not the default.
    from .careers import harvest_emails

    found = [
        {
            "email": email,
            "name": "",
            "title": "",
            "linkedin": "",
            "confidence": 60,
            "source": f"website{path}",
            "verified": 0,
        }
        for email, path in harvest_emails(domain)[:limit]
    ]
    if not found:
        found = _from_hunter(domain, limit)
    if not found:
        found = _from_prospeo(domain, limit)
    if not found and use_scraper:
        found = _from_apify(website or f"https://{domain}")

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for entry in found:
        email = entry["email"].lower()
        if email in seen:
            continue
        seen.add(email)
        unique.append(entry)

    unique.sort(
        key=lambda e: (_role_score(e["title"], e["email"]) + e["confidence"] / 4),
        reverse=True,
    )
    contacts = [
        Contact(
            company_id=company_id,
            email=entry["email"],
            name=entry["name"],
            title=entry["title"],
            linkedin=entry["linkedin"],
            source=entry["source"],
            confidence=entry["confidence"],
            verified=entry["verified"],
        )
        for entry in unique[:limit]
    ]
    log.dim(f"{domain}: {len(contacts)} sendable contact(s)")
    return contacts
