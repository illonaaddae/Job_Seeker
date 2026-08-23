"""Exa semantic search for companies that are not posting on a public board.

This is the cold outreach half of the system: find companies worth writing to,
then hand them to the enrichment step to resolve a human to write to. Kept from
the upstream project because speculative applications genuinely work in the
Ghanaian market, where a lot of hiring never reaches a job board.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ..models import Company
from ..util import env, http, log
from ..util.text import truncate

API = "https://api.exa.ai/search"


def search_companies(query: str, limit: int = 15, category: str = "company") -> list[Company]:
    """Semantic search for companies. Requires EXA_API_KEY."""
    api_key = env.require("EXA_API_KEY")
    payload: dict[str, Any] = {
        "query": query,
        "type": "auto",
        "numResults": max(1, min(limit, 50)),
        "contents": {"text": {"maxCharacters": 2000}},
    }
    if category:
        payload["category"] = category

    log.info(f"Exa search: {query}")
    try:
        data = http.post_json(
            API, json_body=payload, headers={"x-api-key": api_key}, timeout=45
        )
    except Exception as exc:  # noqa: BLE001
        log.warn(f"exa search failed: {exc}")
        return []

    companies: list[Company] = []
    for result in data.get("results", []) if isinstance(data, dict) else []:
        url = result.get("url", "")
        parsed = urlparse(url)
        if not parsed.netloc:
            continue
        raw_title = result.get("title") or parsed.netloc
        # Page titles carry taglines; the company name is the first segment.
        name = raw_title.split(" - ")[0].split(" | ")[0].split(" — ")[0].strip()
        domain = parsed.netloc.removeprefix("www.")
        companies.append(
            Company(
                name=name or domain,
                domain=domain,
                website=f"{parsed.scheme}://{parsed.netloc}",
                source="exa",
                notes=truncate(result.get("text", ""), 600),
            )
        )
    log.dim(f"exa returned {len(companies)} companies")
    return companies


def find_careers_page(company_name: str) -> str:
    """Best effort lookup of a company's careers page, used before scraping."""
    results = search_companies(f"{company_name} careers jobs page", limit=1, category="")
    return results[0].website if results else ""
