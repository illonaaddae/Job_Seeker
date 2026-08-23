"""Authentication for the dashboard.

The server can send email as the account owner, so it must never be reachable
without a login. This module provides that with no third party dependency:

* passwords are stored only as a scrypt hash, never in plain text,
* sessions are HMAC signed cookies with an expiry, so there is no session store
  to keep in sync across restarts or replicas,
* failed logins are throttled per client address, with a lockout, so the single
  password cannot be brute forced,
* the machine to machine path (the scheduled workflow) keeps using a bearer
  token, which is checked in constant time.

Everything here compares secrets with `hmac.compare_digest` so a timing signal
cannot leak the value being compared.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass, field

# scrypt parameters. n=2**15 keeps a single verification around 60ms on a small
# container, which is slow enough to make guessing expensive and fast enough
# that logging in feels instant.
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32

SESSION_COOKIE = "jobseeker_session"
DEFAULT_SESSION_HOURS = 12

# Throttling: after this many failures from one address, that address is locked
# out for the cooldown regardless of whether the next password is correct.
MAX_ATTEMPTS = 8
ATTEMPT_WINDOW_SECONDS = 900     # 15 minutes
LOCKOUT_SECONDS = 900


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


# --------------------------------------------------------------------- passwords


def hash_password(password: str) -> str:
    """Return a self describing scrypt hash, safe to store in an env var."""
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
        maxmem=64 * 1024 * 1024,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant time verification. Any malformed hash is a failure, not an error."""
    if not password or not encoded:
        return False
    try:
        scheme, n, r, p, salt, expected = encoded.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64decode(expected)),
            maxmem=64 * 1024 * 1024,
        )
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(candidate, _b64decode(expected))


# ---------------------------------------------------------------------- sessions


class SessionSigner:
    """Signed, expiring session tokens. Stateless, so restarts do not log you out."""

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("session secret must not be empty")
        self.secret = secret.encode("utf-8")

    def issue(self, subject: str = "owner", hours: int = DEFAULT_SESSION_HOURS) -> str:
        payload = {
            "sub": subject,
            "exp": int(time.time()) + hours * 3600,
            "jti": secrets.token_urlsafe(8),
        }
        body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
        signature = hmac.new(self.secret, body.encode(), hashlib.sha256).digest()
        return f"{body}.{_b64encode(signature)}"

    def verify(self, token: str) -> dict | None:
        """Return the payload, or None for anything tampered with or expired."""
        if not token or "." not in token:
            return None
        body, _, signature = token.partition(".")
        expected = hmac.new(self.secret, body.encode(), hashlib.sha256).digest()
        try:
            supplied = _b64decode(signature)
        except (ValueError, TypeError):
            return None
        if not hmac.compare_digest(expected, supplied):
            return None
        try:
            payload = json.loads(_b64decode(body))
        except (ValueError, TypeError):
            return None
        if not isinstance(payload, dict) or int(payload.get("exp", 0)) < time.time():
            return None
        return payload


# -------------------------------------------------------------------- throttling


@dataclass(slots=True)
class _Attempts:
    failures: list[float] = field(default_factory=list)
    locked_until: float = 0.0


class LoginThrottle:
    """Per client failure counting with a lockout. In memory, which is correct
    here: one replica, and a restart that clears it also clears any progress an
    attacker had made."""

    def __init__(
        self,
        max_attempts: int = MAX_ATTEMPTS,
        window: int = ATTEMPT_WINDOW_SECONDS,
        lockout: int = LOCKOUT_SECONDS,
    ) -> None:
        self.max_attempts = max_attempts
        self.window = window
        self.lockout = lockout
        self._clients: dict[str, _Attempts] = {}
        self._lock = threading.Lock()

    def locked_for(self, client: str) -> int:
        """Seconds remaining on a lockout, or 0 when the client may try."""
        with self._lock:
            record = self._clients.get(client)
            if not record:
                return 0
            remaining = int(record.locked_until - time.time())
            return max(0, remaining)

    def record_failure(self, client: str) -> int:
        """Count a failure. Returns how many attempts are left before lockout."""
        now = time.time()
        with self._lock:
            record = self._clients.setdefault(client, _Attempts())
            record.failures = [t for t in record.failures if now - t < self.window]
            record.failures.append(now)
            if len(record.failures) >= self.max_attempts:
                record.locked_until = now + self.lockout
                record.failures.clear()
                return 0
            return self.max_attempts - len(record.failures)

    def record_success(self, client: str) -> None:
        with self._lock:
            self._clients.pop(client, None)


# ------------------------------------------------------------------------ tokens


def token_matches(supplied: str, expected: str) -> bool:
    if not expected:
        return False
    return hmac.compare_digest(supplied.strip(), expected.strip())
