"""Runtime settings, resolved once from the environment and the boards file."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .util import env

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE = "data/profile.illona.json"
DEFAULT_BOARDS = "data/boards.json"


@dataclass(slots=True)
class Settings:
    profile_path: str = DEFAULT_PROFILE
    boards_path: str = DEFAULT_BOARDS
    db_path: str = "data/jobseeker.db"
    letters_dir: str = "generated/letters"
    cv_dir: str = "generated/cv"

    # Guardrails
    daily_send_cap: int = 12
    per_company_cooldown_days: int = 45
    min_score_to_draft: float = 55.0
    min_score_to_send: float = 62.0
    send_enabled: bool = False
    writer: str = "auto"          # auto | claude | template

    # Discovery
    default_sources: list[str] = field(default_factory=lambda: ["greenhouse", "lever", "ashby"])

    @classmethod
    def load(cls, dotenv_path: str = ".env") -> "Settings":
        env.init(dotenv_path)
        profile = env.get("PROFILE_PATH", DEFAULT_PROFILE) or DEFAULT_PROFILE
        return cls(
            profile_path=profile,
            boards_path=env.get("BOARDS_PATH", DEFAULT_BOARDS) or DEFAULT_BOARDS,
            db_path=env.get("DB_PATH", "data/jobseeker.db") or "data/jobseeker.db",
            letters_dir=env.get("LETTERS_DIR", "generated/letters") or "generated/letters",
            cv_dir=env.get("CV_DIR", "generated/cv") or "generated/cv",
            daily_send_cap=env.get_int("DAILY_SEND_CAP", 12),
            per_company_cooldown_days=env.get_int("PER_COMPANY_COOLDOWN_DAYS", 45),
            min_score_to_draft=float(env.get_int("MIN_SCORE_TO_DRAFT", 55)),
            min_score_to_send=float(env.get_int("MIN_SCORE_TO_SEND", 62)),
            send_enabled=env.get_bool("SEND_ENABLED", False),
            writer=env.get("WRITER", "auto") or "auto",
            default_sources=env.get_list("DEFAULT_SOURCES", ["greenhouse", "lever", "ashby"]),
        )

    def boards(self) -> dict[str, Any]:
        """Board handles grouped by ATS provider, from the boards file."""
        path = Path(self.boards_path)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
