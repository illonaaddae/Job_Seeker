"""JSON API + static host for the dashboard.

Standard library only. It serves the built React dashboard when one exists and
answers the API routes the dashboard calls.

Security posture: this process can send email as the account owner, so nothing
is reachable without proof of identity.

* A person signs in with a password. Only its scrypt hash is ever stored, and a
  successful login sets an HMAC signed, expiring, HttpOnly cookie.
* A machine (the scheduled workflow) sends a bearer token instead.
* Unauthenticated page requests get the login screen. Unauthenticated API
  requests get 401 and nothing else.
* Binding to a public interface without a password configured is refused at
  startup rather than quietly serving an open dashboard.
"""

from __future__ import annotations

import json
import mimetypes
import re
import secrets
import threading
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Pattern
from urllib.parse import parse_qs, urlparse

from ..models import ApplicationStatus, utcnow
from ..pipeline import Pipeline
from ..util import env, log
from . import login_page
from .auth import (
    DEFAULT_SESSION_HOURS,
    SESSION_COOKIE,
    LoginThrottle,
    SessionSigner,
    hash_password,
    token_matches,
    verify_password,
)

DASHBOARD_DIST = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"

Route = tuple[str, Pattern[str], Callable[..., Any]]


def _claude_usable() -> bool:
    try:
        from ..llm.anthropic import is_available

        return is_available()
    except Exception:  # noqa: BLE001
        return False


def _fingerprint(value: str) -> str:
    """A short, non reversible marker so two deployments can be compared without
    either of them revealing the hash."""
    if not value:
        return ""
    import hashlib

    return hashlib.sha256(value.encode()).hexdigest()[:12]


class ApiError(Exception):
    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = status


class Api:
    """Route table. Handlers return plain data and the handler serialises it."""

    def __init__(self, pipeline: Pipeline) -> None:
        self.pipeline = pipeline
        self.db = pipeline.db
        self._lock = threading.Lock()   # long stages must not overlap
        self._signer_cache: tuple[str, SessionSigner] | None = None
        # A discover run takes minutes, and hosts cut requests off long before
        # that: App Service gives up at 230 seconds. So a stage runs on a worker
        # thread and the caller polls for the outcome instead of holding a
        # socket open and hoping.
        self._task: dict[str, Any] = {"stage": None, "status": "idle"}
        self._task_lock = threading.Lock()
        self.routes: list[Route] = [
            ("GET", re.compile(r"^/api/health$"), self.health),
            ("GET", re.compile(r"^/api/stats$"), self.stats),
            ("GET", re.compile(r"^/api/profile$"), self.profile),
            ("GET", re.compile(r"^/api/jobs$"), self.jobs),
            ("GET", re.compile(r"^/api/jobs/(?P<job_id>\d+)$"), self.job_detail),
            ("GET", re.compile(r"^/api/applications$"), self.applications),
            ("GET", re.compile(r"^/api/events$"), self.events),
            ("GET", re.compile(r"^/api/replies$"), self.replies),
            ("GET", re.compile(r"^/api/followups$"), self.followups),
            ("GET", re.compile(r"^/api/run/status$"), self.task_status),
            ("GET", re.compile(r"^/api/jobs/(?P<job_id>\d+)/apply-pack$"), self.apply_pack),
            ("POST", re.compile(r"^/api/jobs/(?P<job_id>\d+)/draft$"), self.draft_job),
            ("POST", re.compile(r"^/api/jobs/(?P<job_id>\d+)/answers$"), self.rebuild_answers),
            ("POST", re.compile(r"^/api/jobs/(?P<job_id>\d+)/status$"), self.set_job_status),
            ("POST", re.compile(r"^/api/applications/(?P<app_id>\d+)/approve$"), self.approve),
            ("POST", re.compile(r"^/api/applications/(?P<app_id>\d+)/status$"), self.set_app_status),
            ("POST", re.compile(r"^/api/run/(?P<stage>[a-z_]+)$"), self.run_stage),
            ("POST", re.compile(r"^/api/jobs/import$"), self.import_url),
            ("GET", re.compile(r"^/api/suppressions$"), self.suppressions),
            ("POST", re.compile(r"^/api/suppressions$"), self.set_suppression),
        ]

    # ----------------------------------------------------------- credentials

    def password_hash(self) -> str:
        """The current password hash.

        A hash set from the dashboard is stored in the database and wins, so a
        password change survives a restart and does not need a redeploy. The
        environment variable is the initial value a deployment ships with.
        """
        return self.password_source()[1]

    def password_source(self) -> tuple[str, str]:
        """Where the password came from, and what it is.

        Reported (without the hash) by the session endpoint, because "the
        password is wrong" is impossible to debug on a deployed instance when
        you cannot tell whether the database or the environment is being read.
        """
        stored = self.db.get_setting("auth_password_hash")
        if stored:
            return "database", stored
        from_env = env.get("AUTH_PASSWORD_HASH", "") or ""
        if from_env:
            return "environment", from_env
        return "none", ""

    def set_password_hash(self, encoded: str) -> None:
        self.db.set_setting("auth_password_hash", encoded)
        # Remember which deployment password this override replaced, so a later
        # deployment that ships a different one is recognised as deliberate.
        self.db.set_setting("auth_password_env_seen", env.get("AUTH_PASSWORD_HASH", "") or "")
        # Rotating the signing secret invalidates every session that was issued
        # under the old password, which is what changing a password should mean.
        self.db.set_setting("session_secret", secrets.token_urlsafe(48))
        self._signer_cache = None

    def signer(self) -> SessionSigner:
        secret = session_secret(self.pipeline)
        if not self._signer_cache or self._signer_cache[0] != secret:
            self._signer_cache = (secret, SessionSigner(secret))
        return self._signer_cache[1]

    # ------------------------------------------------------------- read side

    def health(self, **_: Any) -> dict[str, Any]:
        return {"ok": True, "version": __import__("jobseeker").__version__}

    def stats(self, **_: Any) -> dict[str, Any]:
        return self.pipeline.stats()

    def profile(self, **_: Any) -> dict[str, Any]:
        persona = self.pipeline.persona
        return {
            "identity": persona.identity,
            "targeting": persona.targeting,
            "skills": {
                "core": persona.skill_names(("core",)),
                "secondary": persona.skill_names(("secondary",)),
            },
            "readiness": self._readiness(),
            "settings": {
                "daily_cap": self.pipeline.settings.daily_send_cap,
                "min_score_to_draft": self.pipeline.settings.min_score_to_draft,
                "min_score_to_send": self.pipeline.settings.min_score_to_send,
                "send_enabled": self.pipeline.mailer.send_enabled(),
                "writer": self.pipeline.settings.writer,
            },
        }

    def _readiness(self) -> list[dict[str, Any]]:
        """What is configured, and what is stopping the engine doing more.

        A half configured automation that fails silently is worse than one that
        says plainly which key is missing and what it unlocks.
        """
        checks = [
            {
                "key": "sending",
                "label": "Email sending",
                "ready": bool(env.get("SMTP_PASSWORD") or env.get("GMAIL_APP_PASSWORD")),
                "unlocks": "Actually sending applications and follow ups",
                "how": "Create a Google App Password (needs 2 step verification) and set SMTP_PASSWORD.",
            },
            {
                "key": "inbox",
                "label": "Reading replies",
                "ready": bool(
                    (env.get("IMAP_PASSWORD") or env.get("GMAIL_APP_PASSWORD"))
                    and (env.get("IMAP_USER") or env.get("SENDER_EMAIL"))
                ),
                "unlocks": "Detecting replies, updating the funnel, cancelling follow ups",
                "how": "The same app password works. Set IMAP_PASSWORD.",
            },
            {
                "key": "writer",
                "label": "Letters written by Claude",
                "ready": _claude_usable(),
                "unlocks": "Letters written against each job description rather than from a template",
                "how": (
                    "The key is set but the last call was refused, usually an empty credit "
                    "balance. Top it up and redraft: no restart needed, the engine retries "
                    "on its own. Templates are used meanwhile, which still works."
                    if env.get("ANTHROPIC_API_KEY")
                    else "Set ANTHROPIC_API_KEY to have each letter written against the job description."
                ),
            },
            {
                "key": "live",
                "label": "Live sending switch",
                "ready": self.pipeline.mailer.send_enabled(),
                "unlocks": "Approved applications leaving the building",
                "how": "Set SEND_ENABLED=true once you trust the drafts.",
            },
            {
                "key": "reachable",
                "label": "Companies with a real address",
                "ready": self.db.scalar("SELECT COUNT(*) FROM contacts") > 0,
                "unlocks": "Applications the engine can send without you, rather than portal forms",
                "how": "Run the local prospecting stage. It reads addresses companies publish themselves, no key needed.",
            },
        ]
        return checks

    def jobs(self, query: dict[str, list[str]], **_: Any) -> dict[str, Any]:
        def first(key: str, default: str | None = None) -> str | None:
            values = query.get(key)
            return values[0] if values else default

        min_score = first("min_score")
        limit = int(first("limit", "50") or 50)
        offset = int(first("offset", "0") or 0)
        jobs = self.db.list_jobs(
            status=first("status"),
            min_score=float(min_score) if min_score else None,
            source=first("source"),
            search=first("search"),
            limit=min(limit, 200),
            offset=offset,
        )
        payload = []
        for job in jobs:
            application = self.db.get_application_for_job(int(job.id or 0))
            data = job.to_dict()
            data["application"] = application.to_dict() if application else None
            payload.append(data)
        return {"jobs": payload, "limit": limit, "offset": offset}

    def job_detail(self, job_id: str, **_: Any) -> dict[str, Any]:
        job = self.db.get_job(int(job_id))
        if not job:
            raise ApiError("job not found", HTTPStatus.NOT_FOUND)
        application = self.db.get_application_for_job(int(job.id or 0))
        company = self.db.get_company(int(job.company_id)) if job.company_id else None
        contacts = self.db.list_contacts(int(job.company_id)) if job.company_id else []
        return {
            "job": job.to_dict(),
            "application": application.to_dict() if application else None,
            "company": company.to_dict() if company else None,
            "contacts": [c.to_dict() for c in contacts],
        }

    def apply_pack(self, job_id: str, **_: Any) -> dict[str, Any]:
        """Everything a portal application form asks for, in one place.

        An ATS form cannot be filled by this system, and should not be. What it
        can do is remove the tedium: every answer already exists in the profile
        or the draft, so the work becomes copying rather than composing.
        """
        job = self.db.get_job(int(job_id))
        if not job:
            raise ApiError("job not found", HTTPStatus.NOT_FOUND)

        application = self.db.get_application_for_job(int(job.id or 0))
        persona = self.pipeline.persona
        identity = persona.identity
        name_parts = (identity.get("full_name") or "").split()

        # The strongest paragraph of the letter answers "why this company",
        # which is the one free text box every form has.
        why = ""
        if application and application.body:
            paragraphs = [p for p in application.body.split("\n\n") if p.strip()]
            body_paragraphs = [
                p for p in paragraphs[1:]
                if not p.lower().startswith(("best regards", "hello", "dear"))
            ]
            why = body_paragraphs[0] if body_paragraphs else ""

        fields = [
            {"label": "First name", "value": name_parts[0] if name_parts else "", "group": "you"},
            {"label": "Last name", "value": " ".join(name_parts[1:]), "group": "you"},
            {"label": "Full name", "value": identity.get("full_name", ""), "group": "you"},
            {"label": "Email", "value": identity.get("email", ""), "group": "you"},
            {"label": "Phone", "value": identity.get("phone", ""), "group": "you"},
            {"label": "Location", "value": identity.get("location", ""), "group": "you"},
            {"label": "Pronouns", "value": identity.get("pronouns", ""), "group": "you"},
            {"label": "LinkedIn", "value": identity.get("linkedin", ""), "group": "links"},
            {"label": "GitHub", "value": identity.get("github", ""), "group": "links"},
            {"label": "Portfolio", "value": identity.get("website", ""), "group": "links"},
            {
                "label": "Work authorisation",
                "value": identity.get("work_authorization", ""),
                "group": "logistics",
            },
            {
                "label": "Availability",
                "value": identity.get("availability", ""),
                "group": "logistics",
            },
            {
                "label": "Current role",
                "value": f"{persona.experience[0].get('role')} at {persona.experience[0].get('company')}"
                if persona.experience
                else "",
                "group": "logistics",
            },
            {
                "label": "Education",
                "value": "; ".join(
                    f"{e.get('credential')}, {e.get('institution')} ({e.get('period')})"
                    for e in persona.education[:2]
                ),
                "group": "logistics",
            },
            {
                "label": "Cover letter, full text",
                "value": application.body if application else "",
                "group": "writing",
            },
        ]
        del why

        # The free text questions every form asks, answered from her own bank
        # and cached on the application so reopening the pack is instant and the
        # wording does not drift between visits.
        answers: list[dict[str, Any]] = []
        if application:
            from ..llm.answers import bank_version

            cached = application.form_answers or ""
            if cached:
                try:
                    answers = json.loads(cached)
                except json.JSONDecodeError:
                    answers = []
            # An edit to the answer bank must reach applications that were
            # already opened, so a stale cache is discarded rather than served.
            current_version = bank_version()
            if answers and answers[0].get("version") != current_version:
                answers = []
            if not answers:
                from ..llm.answers import build as build_answers

                answers = build_answers(self.pipeline.persona, job)
                self.db.conn.execute(
                    "UPDATE applications SET form_answers = ? WHERE id = ?",
                    (json.dumps(answers), application.id),
                )

        return {
            "job": job.to_dict(),
            "application": application.to_dict() if application else None,
            "answers": answers,
            "fields": [f for f in fields if f["value"]],
            "documents": [
                {
                    "label": "CV",
                    "filename": Path(application.cv_path).name if application and application.cv_path else "",
                    "url": f"/api/files/cv/{application.id}" if application else "",
                },
                {
                    "label": "Cover letter",
                    "filename": Path(application.cover_letter_path).name
                    if application and application.cover_letter_path
                    else "",
                    "url": f"/api/files/letter/{application.id}" if application else "",
                },
            ]
            if application
            else [],
        }

    def applications(self, query: dict[str, list[str]], **_: Any) -> dict[str, Any]:
        status = (query.get("status") or [None])[0]
        limit = int((query.get("limit") or ["100"])[0])
        apps = self.db.list_applications(status=status, limit=min(limit, 300))
        payload = []
        for application in apps:
            job = self.db.get_job(application.job_id)
            data = application.to_dict()
            data["job"] = job.to_dict() if job else None
            payload.append(data)
        counts = {
            row["status"]: row["n"]
            for row in self.db.query(
                "SELECT status, COUNT(*) AS n FROM applications GROUP BY status"
            )
        }
        counts["all"] = sum(counts.values())
        return {"applications": payload, "counts": counts}

    def events(self, query: dict[str, list[str]], **_: Any) -> dict[str, Any]:
        limit = int((query.get("limit") or ["40"])[0])
        return {"events": self.db.recent_events(min(limit, 200))}

    def replies(self, **_: Any) -> dict[str, Any]:
        return {"replies": [r.to_dict() for r in self.db.list_replies()]}

    def followups(self, **_: Any) -> dict[str, Any]:
        rows = self.db.query(
            "SELECT f.*, a.recipient_email, j.id AS job_id, j.title, j.company_name FROM followups f "
            "JOIN applications a ON a.id = f.application_id "
            "JOIN jobs j ON j.id = a.job_id "
            "WHERE f.status = 'pending' ORDER BY f.due_at ASC LIMIT 50"
        )
        return {"followups": [dict(r) for r in rows]}

    # ------------------------------------------------------------ write side

    def draft_job(self, job_id: str, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        job = self.db.get_job(int(job_id))
        if not job:
            raise ApiError("job not found", HTTPStatus.NOT_FOUND)
        with self._lock:
            application = self.pipeline.draft_one(job, writer_name=body.get("writer"))
        return {"application": application.to_dict()}

    def rebuild_answers(self, job_id: str, **_: Any) -> dict[str, Any]:
        """Regenerate the form answers for one job, tailoring them if possible."""
        job = self.db.get_job(int(job_id))
        if not job:
            raise ApiError("job not found", HTTPStatus.NOT_FOUND)
        application = self.db.get_application_for_job(int(job.id or 0))
        if not application:
            raise ApiError("draft the application first")

        from ..llm.answers import build as build_answers

        with self._lock:
            answers = build_answers(self.pipeline.persona, job)
        self.db.conn.execute(
            "UPDATE applications SET form_answers = ? WHERE id = ?",
            (json.dumps(answers), application.id),
        )
        return {"answers": answers}

    def set_job_status(self, job_id: str, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        status = body.get("status", "")
        if not status:
            raise ApiError("status is required")
        self.db.set_job_status(int(job_id), status)
        return {"ok": True, "job_id": int(job_id), "status": status}

    def approve(self, app_id: str, **_: Any) -> dict[str, Any]:
        result = self.pipeline.approve([int(app_id)])
        if result.messages:
            raise ApiError(result.messages[0])
        return result.to_dict()

    def set_app_status(self, app_id: str, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        status = body.get("status", "")
        if status not in {s.value for s in ApplicationStatus}:
            raise ApiError(f"unknown status '{status}'")

        extra: dict[str, Any] = {}
        application = self.db.get_application(int(app_id))
        if status == ApplicationStatus.SENT and application and not application.sent_at:
            # A portal application is submitted by hand, so this is the only
            # moment the system learns it happened.
            extra["sent_at"] = utcnow()

        self.db.set_application_status(int(app_id), status, **extra)

        if status == ApplicationStatus.SENT and application:
            self.db.set_job_status(application.job_id, "applied")
            self.pipeline.followups.schedule_for(int(app_id), extra.get("sent_at", ""))
        if status in {"replied", "interview", "offer", "rejected"}:
            self.pipeline.followups.cancel_for(int(app_id), f"marked {status} by hand")
        return {"ok": True, "application_id": int(app_id), "status": status}

    def import_url(self, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        url = body.get("url", "").strip()
        if not url.startswith("http"):
            raise ApiError("a job posting URL is required")
        job = self.pipeline.add_job_from_url(
            url, company=body.get("company", ""), title=body.get("title", "")
        )
        if not job:
            raise ApiError("could not read that page")
        return {"job": job.to_dict()}

    def _stage_callables(self, body: dict[str, Any]) -> dict[str, Callable[[], Any]]:
        stages: dict[str, Callable[[], Any]] = {
            "discover": lambda: self.pipeline.discover(body.get("sources")),
            "score": lambda: self.pipeline.score_all(rescore=bool(body.get("rescore"))),
            "draft": lambda: self.pipeline.draft(limit=int(body.get("limit", 10))),
            "send": lambda: self.pipeline.send(
                limit=body.get("limit"), dry_run=not bool(body.get("live"))
            ),
            "followup": lambda: self.pipeline.run_followups(
                limit=int(body.get("limit", 10)), dry_run=not bool(body.get("live"))
            ),
            "replies": lambda: self.pipeline.sync_replies(days=int(body.get("days", 14))),
            "respond": lambda: self.pipeline.respond(
                limit=int(body.get("limit", 10)), dry_run=not bool(body.get("live"))
            ),
            "auto_approve": lambda: self.pipeline.auto_approve(),
            "digest": lambda: self.pipeline.send_digest(dry_run=not bool(body.get("live"))),
            "daily": lambda: {
                "stage": "daily",
                "counts": {},
                "messages": [],
                "items": [s.to_dict() for s in self.pipeline.run_daily(
                    dry_run=not bool(body.get("live"))
                )],
            },
            "prospect_local": lambda: self.pipeline.prospect_local(
                limit=int(body.get("limit", 12)), group=body.get("group", "")
            ),
            "prospect": lambda: self.pipeline.prospect(
                body.get("query", ""), limit=int(body.get("limit", 10))
            ),
        }
        return stages

    def run_stage(self, stage: str, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Start a pipeline stage on a worker thread and return immediately.

        The response says the work began. `task_status` reports how it went.
        """
        stages = self._stage_callables(body)
        if stage not in stages:
            raise ApiError(f"unknown stage '{stage}'", HTTPStatus.NOT_FOUND)

        if stage in {"send", "followup", "respond", "digest", "daily"} and body.get("live"):
            # The API never gets to bypass the master switch.
            if not self.pipeline.mailer.send_enabled():
                raise ApiError(
                    "live sending is disabled. Set SEND_ENABLED=true in the server "
                    "environment to allow it.",
                    HTTPStatus.FORBIDDEN,
                )

        if not self._lock.acquire(blocking=False):
            running = self.task_status().get("stage")
            raise ApiError(f"'{running}' is already running", HTTPStatus.CONFLICT)

        with self._task_lock:
            self._task = {
                "stage": stage,
                "status": "running",
                "started_at": utcnow(),
                "finished_at": "",
                "result": None,
                "error": "",
            }

        def worker() -> None:
            try:
                outcome = stages[stage]()
                payload = outcome.to_dict() if hasattr(outcome, "to_dict") else outcome
                with self._task_lock:
                    self._task.update(
                        status="finished", result=payload, finished_at=utcnow()
                    )
            except Exception as exc:  # noqa: BLE001 - surfaced to the caller as state
                log.error(f"stage '{stage}' failed: {type(exc).__name__}: {exc}")
                with self._task_lock:
                    self._task.update(
                        status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                        finished_at=utcnow(),
                    )
            finally:
                self._lock.release()

        threading.Thread(target=worker, name=f"stage-{stage}", daemon=True).start()
        return {"stage": stage, "status": "running", "started_at": self._task["started_at"]}

    def suppressions(self, **_: Any) -> dict[str, Any]:
        """Addresses and domains no application may ever be sent to."""
        return {"suppressions": self.db.suppression_rows()}

    def set_suppression(self, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Add or remove one suppression.

        A pattern is either a whole address or a domain written `@example.com`,
        which is how `Db.is_suppressed` matches. Removing is a flag on the same
        route rather than a DELETE verb, because the router only speaks GET and
        POST.
        """
        pattern = str(body.get("pattern") or "").strip().lower()
        if not pattern or ("@" not in pattern):
            raise ApiError(
                "pattern must be an address or a domain written as @example.com",
                HTTPStatus.BAD_REQUEST,
            )

        if body.get("remove"):
            removed = self.db.remove_suppression(pattern)
            return {"ok": True, "pattern": pattern, "removed": removed}

        self.db.add_suppression(pattern, str(body.get("reason") or "").strip())
        return {"ok": True, "pattern": pattern, "added": True}

    def task_status(self, **_: Any) -> dict[str, Any]:
        with self._task_lock:
            return dict(self._task)

    # ------------------------------------------------------------- dispatch

    def dispatch(
        self, method: str, path: str, query: dict[str, list[str]], body: dict[str, Any]
    ) -> Any:
        for route_method, pattern, handler in self.routes:
            if route_method != method:
                continue
            match = pattern.match(path)
            if match:
                return handler(query=query, body=body, **match.groupdict())
        raise ApiError(f"no route for {method} {path}", HTTPStatus.NOT_FOUND)


class Handler(BaseHTTPRequestHandler):
    server_version = "JobSeeker"
    api: Api
    token: str
    dist: Path
    throttle: LoginThrottle
    brand: str

    @property
    def password_hash(self) -> str:
        return self.api.password_hash()

    @property
    def signer(self) -> SessionSigner:
        return self.api.signer()

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter default logging
        log.dim(f"{self.address_string()} {fmt % args}")

    # ------------------------------------------------------------- responses

    def _send(
        self,
        status: int,
        payload: Any,
        content_type: str = "application/json",
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        body = (
            json.dumps(payload, default=str).encode()
            if content_type == "application/json"
            else payload
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for header, value in extra_headers or []:
            self.send_header(header, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # ------------------------------------------------------------------ auth

    @property
    def client_key(self) -> str:
        """Identify the caller for throttling. Behind Azure ingress the real
        address is in X-Forwarded-For, and only its first entry is meaningful."""
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "unknown"

    @property
    def is_https(self) -> bool:
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def _cookies(self) -> dict[str, str]:
        raw = self.headers.get("Cookie", "")
        jar: dict[str, str] = {}
        for part in raw.split(";"):
            name, _, value = part.strip().partition("=")
            if name:
                jar[name] = value
        return jar

    def _session_cookie(self, token: str, max_age: int) -> tuple[str, str]:
        attributes = [
            f"{SESSION_COOKIE}={token}",
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            f"Max-Age={max_age}",
        ]
        # Secure would make the cookie unusable over plain http in local use, so
        # it is set only when the request actually arrived over TLS.
        if self.is_https:
            attributes.append("Secure")
        return ("Set-Cookie", "; ".join(attributes))

    def _auth_required(self) -> bool:
        """Auth is off only when no password and no token are configured, which
        is the local development case. `serve()` refuses that combination on a
        public interface."""
        return bool(self.password_hash or self.token)

    def _authorised(self) -> bool:
        if not self._auth_required():
            return True

        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer ") and self.token:
            if token_matches(header.removeprefix("Bearer "), self.token):
                return True

        cookie = self._cookies().get(SESSION_COOKIE, "")
        return bool(cookie) and self.signer.verify(cookie) is not None

    def _json_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 1_000_000:
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return None
        return body if isinstance(body, dict) else None

    def _handle_login(self) -> None:
        # Requiring a JSON content type blocks a cross site HTML form post,
        # which together with SameSite=Lax covers CSRF for this surface.
        if "application/json" not in self.headers.get("Content-Type", ""):
            self._send(HTTPStatus.BAD_REQUEST, {"error": "expected a JSON body"})
            return

        locked = self.throttle.locked_for(self.client_key)
        if locked:
            minutes = max(1, locked // 60)
            self._send(
                HTTPStatus.TOO_MANY_REQUESTS,
                {"error": f"Too many attempts. Try again in {minutes} minute(s)."},
            )
            return

        body = self._json_body() or {}
        password = str(body.get("password", ""))

        if not self.password_hash:
            self._send(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "No password is configured on this server."},
            )
            return

        if not verify_password(password, self.password_hash):
            remaining = self.throttle.record_failure(self.client_key)
            log.warn(f"failed login from {self.client_key}")
            message = (
                "That password is not right."
                if remaining
                else "Too many attempts. This address is locked out for 15 minutes."
            )
            if remaining and remaining <= 3:
                message += f" {remaining} attempt(s) left."
            self._send(HTTPStatus.UNAUTHORIZED, {"error": message})
            return

        self.throttle.record_success(self.client_key)
        hours = env.get_int("SESSION_HOURS", DEFAULT_SESSION_HOURS)
        token = self.signer.issue(hours=hours)
        log.ok(f"signed in from {self.client_key}")
        self._send(
            HTTPStatus.OK,
            {"ok": True},
            extra_headers=[self._session_cookie(token, hours * 3600)],
        )

    def _handle_change_password(self) -> None:
        """Change the sign in password from the dashboard.

        Requires the current password whenever one is set, so a borrowed laptop
        with an open session cannot be used to lock the owner out.
        """
        if "application/json" not in self.headers.get("Content-Type", ""):
            self._send(HTTPStatus.BAD_REQUEST, {"error": "expected a JSON body"})
            return

        existing = self.password_hash
        if existing and not self._authorised():
            self._send(HTTPStatus.UNAUTHORIZED, {"error": "sign in required"})
            return

        locked = self.throttle.locked_for(self.client_key)
        if locked:
            self._send(
                HTTPStatus.TOO_MANY_REQUESTS,
                {"error": f"Too many attempts. Try again in {max(1, locked // 60)} minute(s)."},
            )
            return

        body = self._json_body() or {}
        current = str(body.get("current_password", ""))
        new_password = str(body.get("new_password", ""))

        if existing and not verify_password(current, existing):
            self.throttle.record_failure(self.client_key)
            self._send(HTTPStatus.UNAUTHORIZED, {"error": "The current password is not right."})
            return

        if len(new_password) < 10:
            self._send(
                HTTPStatus.BAD_REQUEST,
                {"error": "Use at least 10 characters. This is the only thing guarding your inbox."},
            )
            return
        if new_password == current:
            self._send(HTTPStatus.BAD_REQUEST, {"error": "That is the password you already have."})
            return

        self.api.set_password_hash(hash_password(new_password))
        self.throttle.record_success(self.client_key)
        log.ok(f"dashboard password changed from {self.client_key}")

        # The rotation above invalidated this session too, so hand back a new one
        # rather than bouncing the person who just changed it to the login screen.
        hours = env.get_int("SESSION_HOURS", DEFAULT_SESSION_HOURS)
        token = self.signer.issue(hours=hours)
        self._send(
            HTTPStatus.OK,
            {"ok": True},
            extra_headers=[self._session_cookie(token, hours * 3600)],
        )

    def _handle_logout(self) -> None:
        self._send(
            HTTPStatus.OK,
            {"ok": True},
            extra_headers=[self._session_cookie("", 0)],
        )

    # --------------------------------------------------------------- methods

    def _serve_document(self, kind: str, application_id: str) -> None:
        application = self.api.db.get_application(int(application_id))
        if not application:
            self._send(HTTPStatus.NOT_FOUND, {"error": "application not found"})
            return

        raw_path = application.cv_path if kind == "cv" else application.cover_letter_path
        target = Path(raw_path).resolve()

        # Only files the engine itself produced, or the configured master CV,
        # may be served. Anything else is a path traversal attempt.
        settings = self.api.pipeline.settings
        allowed_roots = [
            Path(settings.letters_dir).resolve(),
            Path(settings.cv_dir).resolve(),
            Path(self.api.pipeline.persona.cv_path or "x").resolve().parent,
        ]
        if not target.is_file() or not any(
            str(target).startswith(str(root)) for root in allowed_roots
        ):
            self._send(HTTPStatus.NOT_FOUND, {"error": "file not available"})
            return

        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        document = re.match(r"^/api/files/(cv|letter)/(\d+)$", parsed.path)
        if document:
            if not self._authorised():
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "sign in required"})
                return
            self._serve_document(document.group(1), document.group(2))
            return

        if parsed.path == "/auth/session":
            self._send(
                HTTPStatus.OK,
                {
                    "authenticated": self._authorised(),
                    "auth_required": self._auth_required(),
                    "password_set": bool(self.password_hash),
                    "password_source": self.api.password_source()[0],
                    "password_fingerprint": _fingerprint(self.password_hash),
                },
            )
            return

        if parsed.path.startswith("/api/"):
            if not self._authorised():
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "sign in required"})
                return
            try:
                payload = self.api.dispatch(
                    "GET", parsed.path, parse_qs(parsed.query), {}
                )
            except ApiError as exc:
                self._send(exc.status, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                log.error(f"api error: {type(exc).__name__}: {exc}")
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            else:
                self._send(HTTPStatus.OK, payload)
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/auth/login":
            self._handle_login()
            return
        if parsed.path == "/auth/logout":
            self._handle_logout()
            return
        if parsed.path == "/auth/password":
            self._handle_change_password()
            return

        if not self._authorised():
            self._send(HTTPStatus.UNAUTHORIZED, {"error": "sign in required"})
            return
        if "application/json" not in self.headers.get("Content-Type", ""):
            self._send(HTTPStatus.BAD_REQUEST, {"error": "expected a JSON body"})
            return
        body = self._json_body()
        if body is None:
            self._send(HTTPStatus.BAD_REQUEST, {"error": "body must be JSON"})
            return
        try:
            payload = self.api.dispatch("POST", parsed.path, parse_qs(parsed.query), body)
        except ApiError as exc:
            self._send(exc.status, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            log.error(f"api error: {type(exc).__name__}: {exc}")
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
        else:
            self._send(HTTPStatus.OK, payload)

    # ---------------------------------------------------------------- static

    def _serve_static(self, path: str) -> None:
        # No page is reachable without a session. An unauthenticated request for
        # any route gets the login screen, never the dashboard shell.
        if not self._authorised():
            self._send(
                HTTPStatus.OK, login_page.render(self.brand), "text/html; charset=utf-8"
            )
            return

        if not self.dist.exists():
            self._send(
                HTTPStatus.OK,
                b"<h1>JobSeeker API is running</h1><p>Build the dashboard with "
                b"<code>cd dashboard &amp;&amp; npm install &amp;&amp; npm run build</code> "
                b"to serve the UI from here.</p>",
                "text/html; charset=utf-8",
            )
            return

        relative = path.lstrip("/") or "index.html"
        target = (self.dist / relative).resolve()
        # Never serve outside the build directory, whatever the request says.
        if not str(target).startswith(str(self.dist.resolve())) or not target.is_file():
            target = self.dist / "index.html"       # single page app fallback
        if not target.is_file():
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        guessed, _ = mimetypes.guess_type(target.name)
        self._send(
            HTTPStatus.OK, target.read_bytes(), guessed or "application/octet-stream"
        )


def reconcile_password(pipeline: Pipeline) -> str:
    """Decide whether a stored password override still applies.

    A password changed in the dashboard is stored in the database so it survives
    restarts. That must not make the deployment's own password permanently
    unreachable: if it did, a wrong or stale value in the database could never be
    corrected without shell access to the server.

    The rule: an override holds while the deployment password is unchanged. Ship
    a different AUTH_PASSWORD_HASH and that is treated as a deliberate reset, so
    the override is dropped. Redeploying always gets you back in.
    """
    override = pipeline.db.get_setting("auth_password_hash")
    if not override:
        return "environment"

    current_env = env.get("AUTH_PASSWORD_HASH", "") or ""
    seen_env = pipeline.db.get_setting("auth_password_env_seen")

    if current_env and seen_env is not None and current_env != seen_env:
        pipeline.db.conn.execute("DELETE FROM settings WHERE key = 'auth_password_hash'")
        log.warn(
            "The deployed password changed, so the one set from the dashboard was "
            "cleared. Sign in with the deployed password."
        )
        return "environment"

    if current_env and seen_env is None:
        # An override from before this was tracked. It cannot be shown to be
        # deliberate, and an unreachable deployment password is worse than a
        # lost dashboard change, so the deployment wins once.
        pipeline.db.conn.execute("DELETE FROM settings WHERE key = 'auth_password_hash'")
        log.warn(
            "Cleared an untracked dashboard password so the deployed one applies. "
            "Set a new password under Profile if you want a different one."
        )
        return "environment"

    return "database"


def session_secret(pipeline: Pipeline) -> str:
    """A stable signing key. Taken from the environment when set, otherwise
    generated once and kept in the database, so restarts do not sign everyone
    out and there is nothing extra to configure for a local run."""
    configured = env.get("SESSION_SECRET")
    if configured:
        return configured
    stored = pipeline.db.get_setting("session_secret")
    if not stored:
        stored = secrets.token_urlsafe(48)
        pipeline.db.set_setting("session_secret", stored)
    return stored


def build_handler(pipeline: Pipeline, token: str = "") -> type[Handler]:
    namespace = {
        "api": Api(pipeline),
        "token": token,
        "dist": DASHBOARD_DIST,
        "throttle": LoginThrottle(),
        "brand": pipeline.persona.identity.get("brand", "") or "application engine",
    }
    return type("BoundHandler", (Handler,), namespace)


def serve(pipeline: Pipeline, host: str = "127.0.0.1", port: int = 8787) -> None:
    token = env.get("API_TOKEN", "") or ""
    reconcile_password(pipeline)
    # A password set from the dashboard lives in the database, so check both.
    password_hash = (
        pipeline.db.get_setting("auth_password_hash") or env.get("AUTH_PASSWORD_HASH", "") or ""
    )
    public = host not in {"127.0.0.1", "localhost", "::1"}

    if public and not password_hash:
        raise SystemExit(
            "Refusing to listen on a public interface without AUTH_PASSWORD_HASH set.\n"
            "This server can send email as you, so it must not be open.\n"
            "Set a password with:  ./run set-password\n"
            "Or bind to 127.0.0.1 for local use."
        )

    if env.get("AUTH_PASSWORD"):
        raise SystemExit(
            "AUTH_PASSWORD is set. Plain text passwords are never read.\n"
            "Run ./run set-password to generate AUTH_PASSWORD_HASH instead."
        )

    reconcile_password(pipeline)

    handler = build_handler(pipeline, token)
    httpd = ThreadingHTTPServer((host, port), handler)
    log.ok(f"JobSeeker listening on http://{host}:{port}")
    if password_hash:
        log.info("Password sign in is on")
    elif not token:
        log.warn("No password set. Anyone who can reach this port has full access.")
    if token:
        log.info("Bearer token accepted for machine access")
    if not DASHBOARD_DIST.exists():
        log.info("Dashboard build not found. Run: cd dashboard && npm install && npm run dev")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        httpd.server_close()
