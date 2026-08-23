"""Tiny HTTP client over urllib with retries, timeouts and JSON helpers.

Exists so the whole engine stays dependency-free (`requests` not required).
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_TIMEOUT = 30
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 JobSeeker/2.0"
)
RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str) -> None:
        super().__init__(f"HTTP {status} for {url}: {body[:400]}")
        self.status = status
        self.url = url
        self.body = body


@dataclass(slots=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text or "null")


def request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 3,
    backoff: float = 1.5,
) -> Response:
    """Perform an HTTP request, retrying transient failures with backoff."""
    if params:
        query = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}, doseq=True
        )
        url = f"{url}{'&' if '?' in url else '?'}{query}"

    final_headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        "Accept-Encoding": "gzip",
    }
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        final_headers["Content-Type"] = "application/json"
    final_headers.update(headers or {})

    last_error: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=final_headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return Response(resp.status, dict(resp.headers), raw)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            try:
                body = gzip.decompress(body)
            except (OSError, EOFError):
                pass
            text = body.decode("utf-8", errors="replace")
            if exc.code in RETRY_STATUS and attempt < retries - 1:
                last_error = HttpError(exc.code, url, text)
                time.sleep(backoff ** (attempt + 1))
                continue
            raise HttpError(exc.code, url, text) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(backoff ** (attempt + 1))
                continue
            raise
    raise last_error or RuntimeError(f"request to {url} failed")


def get_json(url: str, **kwargs: Any) -> Any:
    return request("GET", url, **kwargs).json()


def post_json(url: str, **kwargs: Any) -> Any:
    return request("POST", url, **kwargs).json()


def get_text(url: str, **kwargs: Any) -> str:
    return request("GET", url, **kwargs).text
