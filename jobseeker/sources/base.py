"""Source interface and registry."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Protocol

from ..models import Job


class SourceError(RuntimeError):
    """A source failed in a way the caller should report but survive."""


class Source(Protocol):
    name: str

    def fetch(self, **kwargs: Any) -> list[Job]: ...


_REGISTRY: dict[str, Callable[..., list[Job]]] = {}


def register(name: str) -> Callable[[Callable[..., list[Job]]], Callable[..., list[Job]]]:
    def decorator(fn: Callable[..., list[Job]]) -> Callable[..., list[Job]]:
        _REGISTRY[name] = fn
        fn.source_name = name  # type: ignore[attr-defined]
        return fn

    return decorator


def registry() -> dict[str, Callable[..., list[Job]]]:
    return dict(_REGISTRY)


def get(name: str) -> Callable[..., list[Job]]:
    if name not in _REGISTRY:
        raise SourceError(f"Unknown source '{name}'. Available: {', '.join(sorted(_REGISTRY))}")
    return _REGISTRY[name]


def dedupe(jobs: Iterable[Job]) -> list[Job]:
    """Collapse the same posting appearing on several boards."""
    seen: set[tuple[str, str]] = set()
    out: list[Job] = []
    for job in jobs:
        fingerprint = (job.company_name.strip().lower(), job.title.strip().lower())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        out.append(job)
    return out
