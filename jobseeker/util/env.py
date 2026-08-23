"""Environment loading: `.env` file merged over real process environment."""

from __future__ import annotations

import os
from pathlib import Path

_LOADED: dict[str, str] = {}


def load_dotenv(path: str | os.PathLike[str] = ".env") -> dict[str, str]:
    """Parse a `.env` file into a dict. Missing file is not an error.

    Supports `KEY=value`, `export KEY=value`, `#` comments, and quoted values.
    """
    values: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return values
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def init(path: str | os.PathLike[str] = ".env") -> None:
    """Load the `.env` file once into the module cache."""
    global _LOADED
    _LOADED = load_dotenv(path)


def get(key: str, default: str | None = None) -> str | None:
    """Real environment wins over `.env` so CI/container secrets override files."""
    if key in os.environ and os.environ[key] != "":
        return os.environ[key]
    value = _LOADED.get(key)
    return value if value not in (None, "") else default


def get_bool(key: str, default: bool = False) -> bool:
    value = get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int(key: str, default: int) -> int:
    value = get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def get_list(key: str, default: list[str] | None = None) -> list[str]:
    value = get(key)
    if not value:
        return list(default or [])
    return [part.strip() for part in value.split(",") if part.strip()]


def require(key: str) -> str:
    value = get(key)
    if not value:
        raise MissingCredential(key)
    return value


class MissingCredential(RuntimeError):
    def __init__(self, key: str) -> None:
        super().__init__(
            f"{key} is not set. Add it to your .env file (see .env.example) "
            f"or export it in your shell."
        )
        self.key = key
