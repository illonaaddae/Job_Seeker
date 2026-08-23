"""HTTP API for the dashboard, built on http.server so nothing extra installs."""

from .app import build_handler, serve

__all__ = ["serve", "build_handler"]
