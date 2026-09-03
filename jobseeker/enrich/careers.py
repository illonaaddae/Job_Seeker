"""Finding a real address to write to, using nothing but the public web.

Hunter, Prospeo and Apify all want a paid key. Most companies publish a hiring
address on their own site anyway, so this resolves a company to its domain and
reads the pages where such an address normally lives.

It is deliberately conservative: it only keeps addresses on the company's own
domain, it drops the ones no application should ever go to, and it prefers a
careers or jobs inbox over a generic one.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from ..models import Contact
from ..util import http, log
from ..util.text import normalize
from .finder import BLOCKED_LOCAL_PARTS, PREFERRED_LOCAL_PARTS, _is_sendable, _local_part

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_MAILTO_RE = re.compile(r'mailto:([^"\'?>\s]+)', re.I)

# Pages that carry a hiring address, in the order worth trying.
CANDIDATE_PATHS = (
    "/careers", "/jobs", "/careers/contact", "/about/careers",
    "/contact", "/contact-us", "/about", "/about-us", "/",
)

# Suffixes to try when a company's domain is not already known.
DOMAIN_SUFFIXES = (".com", ".io", ".co", ".ai", ".dev", ".org", ".net")

# ATS and aggregator hosts are never the employer's own domain.
NOT_COMPANY_HOSTS = (
    "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "myworkdayjobs.com",
    "remoteok.com", "arbeitnow.com", "linkedin.com", "indeed.com", "glassdoor.com",
    "smartrecruiters.com", "bamboohr.com", "recruitee.com", "teamtailor.com",
)


def _slug(company_name: str) -> str:
    cleaned = normalize(company_name)
    cleaned = re.sub(r"\b(inc|ltd|limited|llc|gmbh|plc|corp|corporation|co|technologies|technology|labs|group)\b", "", cleaned)
    return re.sub(r"[^a-z0-9]", "", cleaned)


def guess_domain(company_name: str, known_url: str = "") -> str:
    """Resolve a company to its own domain, avoiding ATS hosts."""
    if known_url:
        # Accept either a full URL or a bare domain, because callers have both.
        candidate = known_url.strip()
        if "://" not in candidate:
            candidate = f"https://{candidate}"
        host = urlparse(candidate).netloc.removeprefix("www.").lower()
        if host and not any(host.endswith(bad) for bad in NOT_COMPANY_HOSTS):
            return host

    slug = _slug(company_name)
    if len(slug) < 3:
        return ""

    for suffix in DOMAIN_SUFFIXES:
        candidate = f"{slug}{suffix}"
        try:
            response = http.request("GET", f"https://{candidate}", timeout=10, retries=1)
        except Exception:  # noqa: BLE001 - a domain that does not resolve is just a miss
            continue
        if response.status < 400:
            body = response.text[:4000].lower()
            # Confirm the page actually belongs to this company, so a squatted
            # domain does not get mistaken for the employer.
            if slug[:6] in re.sub(r"[^a-z0-9]", "", body):
                log.dim(f"resolved {company_name} to {candidate}")
                return candidate
    return ""


def harvest_emails(domain: str, max_pages: int = 5) -> list[tuple[str, str]]:
    """Return (email, source path) pairs found on the company's own pages."""
    if not domain:
        return []

    found: dict[str, str] = {}
    base = f"https://{domain}"

    for path in CANDIDATE_PATHS[:max_pages]:
        url = urljoin(base, path)
        try:
            html = http.get_text(url, timeout=12, retries=1)
        except Exception:  # noqa: BLE001
            continue

        candidates = set(_MAILTO_RE.findall(html)) | set(_EMAIL_RE.findall(html))
        for raw in candidates:
            email = raw.strip().strip(".,;:").lower()
            if not _is_sendable(email):
                continue
            # Only the company's own domain. A third party address on their site
            # belongs to someone else.
            if not email.endswith(f"@{domain}") and domain not in email.split("@")[-1]:
                continue
            found.setdefault(email, path)

        # Compare the local part exactly. A substring test against the whole
        # address means a trap called "antispamproofcareers@" reads as a
        # careers inbox, and the crawl stops on the worst possible match.
        if any(_local_part(address) in PREFERRED_LOCAL_PARTS for address in found):
            break   # a real hiring inbox was found, no need to keep crawling

    return sorted(found.items(), key=lambda pair: _rank(pair[0]), reverse=True)


def _rank(email: str) -> int:
    local = email.split("@")[0].lower()
    if local in ("careers", "jobs", "recruitment", "recruiting", "talent", "hiring"):
        return 100
    if local in ("hr", "people"):
        return 80
    if local in ("hello", "contact", "info", "team"):
        return 40
    if "." in local:
        return 60      # firstname.lastname is a real person
    return 20


def find_contacts_free(
    company_id: int, company_name: str, known_url: str = "", limit: int = 3
) -> list[Contact]:
    """Contact discovery with no API key and no cost."""
    domain = guess_domain(company_name, known_url)
    if not domain:
        log.dim(f"no public domain found for {company_name}")
        return []

    harvested = harvest_emails(domain)
    contacts = [
        Contact(
            company_id=company_id,
            email=email,
            name="",
            title="",
            source=f"website{path}",
            confidence=min(95, _rank(email)),
            verified=0,
        )
        for email, path in harvested[:limit]
    ]
    log.dim(f"{company_name} ({domain}): {len(contacts)} address(es) from the public site")
    return contacts


__all__ = ["find_contacts_free", "guess_domain", "harvest_emails", "BLOCKED_LOCAL_PARTS"]
