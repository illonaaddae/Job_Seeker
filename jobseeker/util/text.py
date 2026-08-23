"""Text normalisation helpers shared by scoring, parsing and PDF layout."""

from __future__ import annotations

import html
import re
import unicodedata
from functools import lru_cache

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t ]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")

# Words that carry no signal when matching a CV against a job description.
STOPWORDS = frozenset(
    """
    a an the and or but if then else for to of in on at by with without from as is are was were be
    been being do does did doing have has had having you your we our us they their it its this that
    these those will would shall should can could may might must not no nor so than too very just
    about into over under again further once here there when where why how all any both each few
    more most other some such only own same s t don now who whom which what while during before
    after above below up down out off role roles job jobs work working team teams company companies
    experience experiences year years position candidate candidates you'll we're
    """.split()
)


def strip_html(value: str) -> str:
    """Turn an HTML job description into readable plain text."""
    if not value:
        return ""
    text = value
    # Some boards (Greenhouse in particular) return HTML that is itself entity
    # encoded, so the tags only appear after the first unescape. Unescape, strip,
    # then unescape again to catch entities that were nested inside the markup.
    if "&lt;" in text or "&amp;" in text:
        text = html.unescape(text)
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _MULTI_NL_RE.sub("\n\n", text).strip()


def normalize(value: str) -> str:
    """Lowercase, strip accents, collapse whitespace — for comparisons only."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _WS_RE.sub(" ", ascii_only.lower()).strip()


def tokens(value: str) -> list[str]:
    """Content tokens with stopwords removed. Keeps `c++`, `node.js`, `ci/cd` shapes."""
    return [t for t in _TOKEN_RE.findall(normalize(value)) if t not in STOPWORDS and len(t) > 1]


def token_set(value: str) -> set[str]:
    return set(tokens(value))


@lru_cache(maxsize=4096)
def normalised_phrase(phrase: str) -> str:
    return normalize(phrase)


@lru_cache(maxsize=4096)
def phrase_pattern(phrase: str) -> re.Pattern[str] | None:
    """Compile and cache a whole-phrase matcher. Phrases repeat across thousands
    of jobs, so compiling once is the difference between seconds and minutes."""
    normalised = normalize(phrase)
    if not normalised:
        return None
    return re.compile(rf"(?<![a-z0-9]){re.escape(normalised)}(?![a-z0-9])")


def contains_phrase(haystack: str, phrase: str, *, normalised: bool = False) -> bool:
    """Whole-phrase match that tolerates punctuation and casing differences.

    Pass `normalised=True` when the haystack has already been through
    `normalize()`, which avoids re-normalising the same job description once per
    skill lookup.
    """
    needle = normalised_phrase(phrase)
    if not needle:
        return False

    text = haystack if normalised else normalize(haystack)

    # Almost every check is a miss, and a plain substring scan rejects those far
    # faster than the boundary aware regex. Only run the regex on the rare hit,
    # where the word boundaries actually have to be verified.
    if needle not in text:
        return False

    pattern = phrase_pattern(phrase)
    return pattern is not None and pattern.search(text) is not None


def truncate(value: str, limit: int, suffix: str = "…") -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - len(suffix))].rstrip() + suffix


def slugify(value: str, max_length: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize(value)).strip("-")
    return slug[:max_length] or "untitled"


def sentences(value: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", value.strip())
    return [p.strip() for p in parts if p.strip()]
