"""Voice enforcement for everything this system writes.

Two non-negotiable house rules, applied to every generated email, letter and
summary regardless of which generator produced it:

1. No em dashes or en dashes anywhere. They are the clearest tell of machine
   written text and they are not how Illona writes.
2. Nothing generic. A sentence that would survive a find and replace of the
   company name is not worth sending.

`sanitise()` is a hard guarantee applied after generation. `audit()` is the
soft check that reports what still reads as filler so a draft can be rejected
or regenerated before a human ever sees it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Dash characters that must never reach a recipient.
DASHES = "—–―‒﹘‑⁃"
_DASH_RE = re.compile(f"[{DASHES}]")

# Filler that signals machine authorship or says nothing about the reader.
BANNED_PHRASES: tuple[str, ...] = (
    "i am excited to", "i'm excited to", "i am thrilled", "i'm thrilled",
    "passionate about", "leverage", "delve", "in today's fast-paced",
    "seamlessly", "robust solution", "cutting-edge", "cutting edge",
    "game-changer", "game changer", "synergy", "best-in-class", "world-class",
    "dynamic environment", "i hope this email finds you well",
    "i hope this finds you well", "as an ai", "it is worth noting", "unlock",
    "elevate", "embark", "tapestry", "testament to", "at the end of the day",
    "wealth of experience", "proven track record", "results-driven",
    "hit the ground running", "think outside the box", "team player",
    "detail-oriented", "self-starter", "i believe i would be a great fit",
    "perfect candidate", "dream job", "your esteemed company",
    "esteemed organisation", "esteemed organization", "kindly note",
    "furthermore", "moreover", "in conclusion", "firstly", "utilise cutting",
    "deep dive", "circle back", "move the needle", "low-hanging fruit",
    "i am writing to express my strong interest",
)

# Straight replacements applied before the generic dash rule, so the sentence
# still reads naturally rather than collapsing into comma soup.
_PHRASE_FIXES: tuple[tuple[str, str], ...] = (
    (r"\bI am writing to express my strong interest in\b", "I am applying for"),
    (r"\bI am writing to express my interest in\b", "I am applying for"),
    (r"\bI would like to express my interest in\b", "I am applying for"),
    (r"\bI hope this email finds you well\.?\s*", ""),
    (r"\bI hope this finds you well\.?\s*", ""),
    (r"\bleverage\b", "use"),
    (r"\bLeverage\b", "Use"),
    (r"\bleveraging\b", "using"),
    (r"\butilis[ez]\b", "use"),
    (r"\bdelve into\b", "look at"),
    (r"\bcutting[- ]edge\b", "current"),
    (r"\bseamlessly\b", "cleanly"),
    (r"\bpassionate about\b", "focused on"),
    (r"\bin today's fast[- ]paced\b", "in this"),
    (r"\bfurthermore,?\s*", ""),
    (r"\bMoreover,?\s*", ""),
    (r"\bmoreover,?\s*", ""),
)

_SPACES = re.compile(r"[ \t]{2,}")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")
_DOUBLE_PUNCT = re.compile(r",\s*,+")
_ORPHAN_COMMA = re.compile(r"(^|\n)\s*,\s*")


def replace_dashes(value: str) -> str:
    """Turn dashes into punctuation that carries the same meaning.

    A dash between two spaces becomes a comma. A dash joining two words with no
    spaces becomes a hyphen, which is ordinary typing and stays allowed.
    """
    if not value:
        return value
    out = re.sub(rf"\s+[{DASHES}]\s+", ", ", value)
    out = re.sub(rf"(?<=\w)[{DASHES}](?=\w)", "-", out)
    out = _DASH_RE.sub(", ", out)
    return out


def sanitise(value: str) -> str:
    """Apply every house rule. Safe to run on already clean text."""
    if not value:
        return value
    out = value
    for pattern, replacement in _PHRASE_FIXES:
        out = re.sub(pattern, replacement, out)
    out = replace_dashes(out)
    out = _DOUBLE_PUNCT.sub(",", out)
    out = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    out = _ORPHAN_COMMA.sub(r"\1", out)
    out = _SPACES.sub(" ", out)
    out = "\n".join(line.rstrip() for line in out.splitlines())
    out = re.sub(r"\n{3,}", "\n\n", out)
    # A comma directly before a full stop is the usual artefact of dash removal.
    out = re.sub(r",\s*\.", ".", out)
    # A dash at the end of a line becomes a trailing comma, which reads wrong.
    # Salutation and sign off commas ("Dear Ada," / "Best,") must survive, so only
    # strip a line final comma when the line is a full sentence.
    out = "\n".join(
        re.sub(r",$", "", line) if len(line.split()) > 6 else line
        for line in out.splitlines()
    )
    return out.strip()


@dataclass(slots=True)
class StyleReport:
    """What a draft still gets wrong, and whether it is good enough to send."""

    dashes: int = 0
    banned: list[str] = field(default_factory=list)
    word_count: int = 0
    specificity_hits: list[str] = field(default_factory=list)
    missing_specifics: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return self.dashes == 0 and not self.banned and not self.missing_specifics

    def summary(self) -> str:
        if self.clean:
            return f"clean ({self.word_count} words)"
        problems = []
        if self.dashes:
            problems.append(f"{self.dashes} dash(es)")
        if self.banned:
            problems.append("filler: " + ", ".join(self.banned[:4]))
        if self.missing_specifics:
            problems.append("not specific: " + ", ".join(self.missing_specifics))
        return "; ".join(problems)


def audit(
    text: str,
    *,
    company: str = "",
    job_title: str = "",
    require_specifics: bool = True,
    max_words: int | None = None,
) -> StyleReport:
    """Grade a draft for dashes, filler and whether it says anything concrete."""
    report = StyleReport()
    if not text:
        report.missing_specifics.append("empty draft")
        return report

    lowered = text.lower()
    report.dashes = len(_DASH_RE.findall(text))
    report.banned = [p for p in BANNED_PHRASES if p in lowered]
    report.word_count = len(text.split())

    if require_specifics:
        if company and company.lower().split()[0] in lowered:
            report.specificity_hits.append("names the company")
        else:
            report.missing_specifics.append("never names the company")

        if job_title and any(
            word in lowered for word in job_title.lower().split() if len(word) > 3
        ):
            report.specificity_hits.append("names the role")
        else:
            report.missing_specifics.append("never names the role")

        # Concrete evidence looks like a number, a URL or a named technology.
        if re.search(r"\b\d", text) or "oceaniccoder.dev" in lowered or "github.com" in lowered:
            report.specificity_hits.append("cites concrete evidence")
        else:
            report.missing_specifics.append("no number, link or artefact cited")

    if max_words and report.word_count > max_words:
        report.missing_specifics.append(f"too long ({report.word_count} > {max_words} words)")

    return report


def enforce(
    text: str,
    *,
    company: str = "",
    job_title: str = "",
    max_words: int | None = None,
    require_specifics: bool = True,
) -> tuple[str, StyleReport]:
    """Sanitise then audit. The returned text is always safe to send."""
    cleaned = sanitise(text)
    return cleaned, audit(
        cleaned,
        company=company,
        job_title=job_title,
        max_words=max_words,
        require_specifics=require_specifics,
    )


def style_prompt_block() -> str:
    """The writing constraints handed to any LLM that drafts for this system."""
    return (
        "WRITING RULES, these are absolute:\n"
        "1. Never use an em dash or an en dash. Not once. Use a comma, a full stop "
        "or a colon. Ordinary hyphens inside compound words are fine.\n"
        "2. Never use any of these phrases: "
        + ", ".join(f'"{p}"' for p in BANNED_PHRASES[:22])
        + ".\n"
        "3. Do not open by hoping the reader is well, and do not compliment the "
        "company in the abstract.\n"
        "4. Every paragraph must contain something that is only true of this "
        "specific role and this specific applicant. If a sentence would still "
        "make sense with a different company name pasted in, delete it.\n"
        "5. Reference at least one concrete detail lifted from the job "
        "description itself, and at least one concrete artefact from the "
        "applicant's work, with a number, a named technology or a link.\n"
        "6. Short sentences. Plain words. British spelling. No corporate "
        "vocabulary, no enthusiasm padding, no summary of what was just said.\n"
        "7. Never claim seniority, years of experience or technologies that are "
        "not in the profile provided.\n"
    )
