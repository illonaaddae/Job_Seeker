"""Console logging with a consistent, quiet-by-default house style."""

from __future__ import annotations

import sys
from typing import Any

_QUIET = False
_NO_COLOR = False

_COLORS = {
    "info": "\033[36m",
    "ok": "\033[32m",
    "warn": "\033[33m",
    "error": "\033[31m",
    "dim": "\033[90m",
    "bold": "\033[1m",
}
_RESET = "\033[0m"


def configure(quiet: bool = False, no_color: bool = False) -> None:
    global _QUIET, _NO_COLOR
    _QUIET = quiet
    _NO_COLOR = no_color or not sys.stdout.isatty()


def _paint(style: str, text: str) -> str:
    if _NO_COLOR or style not in _COLORS:
        return text
    return f"{_COLORS[style]}{text}{_RESET}"


def _emit(style: str, symbol: str, message: str, stream: Any = sys.stdout) -> None:
    if _QUIET and style in {"info", "dim"}:
        return
    print(f"{_paint(style, symbol)} {message}", file=stream, flush=True)


def info(message: str) -> None:
    _emit("info", "·", message)


def ok(message: str) -> None:
    _emit("ok", "✓", message)


def warn(message: str) -> None:
    _emit("warn", "!", message, stream=sys.stderr)


def error(message: str) -> None:
    _emit("error", "✗", message, stream=sys.stderr)


def dim(message: str) -> None:
    _emit("dim", " ", _paint("dim", message))


def header(message: str) -> None:
    if _QUIET:
        return
    print(f"\n{_paint('bold', message)}", flush=True)
