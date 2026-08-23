"""SQLite persistence layer.

One file, one schema, no ORM. The upstream project used CSV files, which lost
rows on concurrent writes and could not express relationships between a job,
the company, the contact and the follow-up thread. Everything here is
transactional and safe to run from CLI, API server and cron at the same time.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

from .models import (
    Application,
    ApplicationStatus,
    Company,
    Contact,
    Event,
    Followup,
    Job,
    JobStatus,
    Reply,
    utcnow,
)

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    domain       TEXT DEFAULT '',
    website      TEXT DEFAULT '',
    careers_url  TEXT DEFAULT '',
    source       TEXT DEFAULT '',
    industry     TEXT DEFAULT '',
    location     TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_name ON companies(lower(name));
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);

CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    company_name    TEXT NOT NULL,
    source          TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    title           TEXT NOT NULL,
    url             TEXT DEFAULT '',
    location        TEXT DEFAULT '',
    remote          INTEGER DEFAULT 0,
    employment_type TEXT DEFAULT '',
    department      TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    salary          TEXT DEFAULT '',
    posted_at       TEXT DEFAULT '',
    score           REAL DEFAULT 0,
    score_breakdown TEXT DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'new',
    discovered_at   TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_external ON jobs(source, external_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);

CREATE TABLE IF NOT EXISTS contacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        TEXT DEFAULT '',
    title       TEXT DEFAULT '',
    email       TEXT NOT NULL,
    linkedin    TEXT DEFAULT '',
    source      TEXT DEFAULT '',
    confidence  INTEGER DEFAULT 0,
    verified    INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_email ON contacts(lower(email));

CREATE TABLE IF NOT EXISTS applications (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id            INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    company_id        INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    contact_id        INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    channel           TEXT NOT NULL DEFAULT 'email',
    status            TEXT NOT NULL DEFAULT 'draft',
    recipient_email   TEXT DEFAULT '',
    subject           TEXT DEFAULT '',
    body              TEXT DEFAULT '',
    cover_letter_path TEXT DEFAULT '',
    cv_path           TEXT DEFAULT '',
    tailored_summary  TEXT DEFAULT '',
    message_id        TEXT DEFAULT '',
    thread_refs       TEXT DEFAULT '',
    generator         TEXT DEFAULT '',
    sent_at           TEXT DEFAULT '',
    notes             TEXT DEFAULT '',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);

CREATE TABLE IF NOT EXISTS followups (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    sequence_no    INTEGER NOT NULL,
    due_at         TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    sent_at        TEXT DEFAULT '',
    message_id     TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_followups_seq ON followups(application_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_followups_due ON followups(status, due_at);

CREATE TABLE IF NOT EXISTS replies (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    from_addr      TEXT NOT NULL,
    subject        TEXT DEFAULT '',
    snippet        TEXT DEFAULT '',
    classification TEXT DEFAULT 'unknown',
    received_at    TEXT NOT NULL,
    uid            TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_replies_uid ON replies(uid) WHERE uid <> '';

CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    type           TEXT NOT NULL,
    message        TEXT DEFAULT '',
    job_id         INTEGER,
    application_id INTEGER,
    payload        TEXT DEFAULT '{}',
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC);

CREATE TABLE IF NOT EXISTS suppressions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern    TEXT NOT NULL UNIQUE,
    reason     TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_local = threading.local()


class Database:
    """Thread-safe SQLite wrapper. One connection per thread."""

    def __init__(self, path: str | Path, journal_mode: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # WAL is right on a local disk, but it needs shared memory, which SMB
        # network shares such as Azure Files do not provide. On those, WAL either
        # fails outright or produces "database is locked" under any concurrency,
        # so deployments on a mounted share set SQLITE_JOURNAL_MODE=TRUNCATE.
        self.journal_mode = (
            journal_mode or os.environ.get("SQLITE_JOURNAL_MODE") or "WAL"
        ).upper()
        self._init_schema()

    # ---------------------------------------------------------------- plumbing

    @property
    def conn(self) -> sqlite3.Connection:
        key = f"conn_{id(self)}"
        conn = getattr(_local, key, None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA journal_mode={self.journal_mode}")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
            setattr(_local, key, conn)
        return conn

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.set_setting("schema_version", str(SCHEMA_VERSION))

    def _migrate(self) -> None:
        """Add columns that arrived after a database was first created.

        `CREATE TABLE IF NOT EXISTS` silently does nothing for an existing table,
        so new columns have to be added explicitly. Each one is guarded, which
        makes this safe to run on every start.
        """
        additions = {
            "applications": {
                "form_answers": "TEXT DEFAULT '{}'",
            },
            "replies": {
                "draft_subject": "TEXT DEFAULT ''",
                "draft_body": "TEXT DEFAULT ''",
                "draft_status": "TEXT DEFAULT 'none'",
                "draft_generator": "TEXT DEFAULT ''",
                "responded_at": "TEXT DEFAULT ''",
                "message_id": "TEXT DEFAULT ''",
            },
        }
        for table, columns in additions.items():
            existing = {row["name"] for row in self.query(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except Exception:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, tuple(params)))

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        row = self.one(sql, params)
        return row[0] if row else None

    # ---------------------------------------------------------------- settings

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    # --------------------------------------------------------------- companies

    def upsert_company(self, company: Company) -> int:
        existing = self.one(
            "SELECT * FROM companies WHERE lower(name) = lower(?)", (company.name,)
        )
        if existing:
            company_id = int(existing["id"])
            # Only fill blanks — never overwrite curated data with scraped guesses.
            updates = {
                col: getattr(company, col)
                for col in ("domain", "website", "careers_url", "industry", "location")
                if getattr(company, col) and not existing[col]
            }
            if updates:
                assignments = ", ".join(f"{col} = ?" for col in updates)
                self.conn.execute(
                    f"UPDATE companies SET {assignments} WHERE id = ?",
                    (*updates.values(), company_id),
                )
            return company_id
        cur = self.conn.execute(
            "INSERT INTO companies(name, domain, website, careers_url, source, industry, "
            "location, notes, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                company.name,
                company.domain,
                company.website,
                company.careers_url,
                company.source,
                company.industry,
                company.location,
                company.notes,
                company.created_at,
            ),
        )
        return int(cur.lastrowid or 0)

    def get_company(self, company_id: int) -> Company | None:
        row = self.one("SELECT * FROM companies WHERE id = ?", (company_id,))
        return Company.from_row(row) if row else None

    def find_company_by_name(self, name: str) -> Company | None:
        row = self.one("SELECT * FROM companies WHERE lower(name) = lower(?)", (name,))
        return Company.from_row(row) if row else None

    # -------------------------------------------------------------------- jobs

    def upsert_job(self, job: Job) -> tuple[int, bool]:
        """Insert a job, or refresh a known one. Returns (job_id, was_new)."""
        existing = self.one(
            "SELECT id FROM jobs WHERE source = ? AND external_id = ?",
            (job.source, job.external_id),
        )
        if existing:
            job_id = int(existing["id"])
            self.conn.execute(
                "UPDATE jobs SET title=?, url=?, location=?, remote=?, employment_type=?, "
                "department=?, description=?, salary=?, posted_at=?, company_id=COALESCE(?, company_id) "
                "WHERE id=?",
                (
                    job.title,
                    job.url,
                    job.location,
                    job.remote,
                    job.employment_type,
                    job.department,
                    job.description,
                    job.salary,
                    job.posted_at,
                    job.company_id,
                    job_id,
                ),
            )
            return job_id, False
        cur = self.conn.execute(
            "INSERT INTO jobs(company_id, company_name, source, external_id, title, url, location, "
            "remote, employment_type, department, description, salary, posted_at, score, "
            "score_breakdown, status, discovered_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                job.company_id,
                job.company_name,
                job.source,
                job.external_id,
                job.title,
                job.url,
                job.location,
                job.remote,
                job.employment_type,
                job.department,
                job.description,
                job.salary,
                job.posted_at,
                job.score,
                json.dumps(job.score_breakdown),
                job.status,
                job.discovered_at,
            ),
        )
        return int(cur.lastrowid or 0), True

    def get_job(self, job_id: int) -> Job | None:
        row = self.one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        return Job.from_row(row) if row else None

    def list_jobs(
        self,
        *,
        status: str | None = None,
        min_score: float | None = None,
        source: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "score DESC, discovered_at DESC",
    ) -> list[Job]:
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if min_score is not None:
            clauses.append("score >= ?")
            params.append(min_score)
        if source:
            clauses.append("source = ?")
            params.append(source)
        if search:
            clauses.append("(title LIKE ? OR company_name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.query(
            f"SELECT * FROM jobs {where} ORDER BY {order} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return [Job.from_row(r) for r in rows]

    def update_job_score(self, job_id: int, score: float, breakdown: dict[str, Any]) -> None:
        self.conn.execute(
            "UPDATE jobs SET score = ?, score_breakdown = ?, "
            "status = CASE WHEN status = 'new' THEN 'scored' ELSE status END WHERE id = ?",
            (score, json.dumps(breakdown), job_id),
        )

    def set_job_status(self, job_id: int, status: str | JobStatus) -> None:
        self.conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (str(status), job_id))

    # ---------------------------------------------------------------- contacts

    def upsert_contact(self, contact: Contact) -> int:
        existing = self.one(
            "SELECT id FROM contacts WHERE lower(email) = lower(?)", (contact.email,)
        )
        if existing:
            return int(existing["id"])
        cur = self.conn.execute(
            "INSERT INTO contacts(company_id, name, title, email, linkedin, source, confidence, "
            "verified, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                contact.company_id,
                contact.name,
                contact.title,
                contact.email,
                contact.linkedin,
                contact.source,
                contact.confidence,
                contact.verified,
                contact.created_at,
            ),
        )
        return int(cur.lastrowid or 0)

    def best_contact_for_company(self, company_id: int) -> Contact | None:
        row = self.one(
            "SELECT * FROM contacts WHERE company_id = ? "
            "ORDER BY verified DESC, confidence DESC, id ASC LIMIT 1",
            (company_id,),
        )
        return Contact.from_row(row) if row else None

    def list_contacts(self, company_id: int | None = None) -> list[Contact]:
        if company_id is None:
            rows = self.query("SELECT * FROM contacts ORDER BY id DESC LIMIT 500")
        else:
            rows = self.query("SELECT * FROM contacts WHERE company_id = ?", (company_id,))
        return [Contact.from_row(r) for r in rows]

    # ------------------------------------------------------------ applications

    def upsert_application(self, app: Application) -> int:
        existing = self.one(
            "SELECT id, status, sent_at, message_id FROM applications WHERE job_id = ?",
            (app.job_id,),
        )
        now = utcnow()
        if existing:
            app_id = int(existing["id"])

            # Rewriting the letter must not undo a decision about it. An
            # approval is a human act, and something already sent is history.
            protected = {"approved", "sent", "replied", "interview", "offer", "rejected", "ghosted"}
            status = existing["status"] if existing["status"] in protected else app.status

            self.conn.execute(
                "UPDATE applications SET company_id=?, contact_id=?, channel=?, status=?, "
                "recipient_email=?, subject=?, body=?, cover_letter_path=?, cv_path=?, "
                "tailored_summary=?, generator=?, notes=?, updated_at=? WHERE id=?",
                (
                    app.company_id,
                    app.contact_id,
                    app.channel,
                    status,
                    app.recipient_email,
                    app.subject,
                    app.body,
                    app.cover_letter_path,
                    app.cv_path,
                    app.tailored_summary,
                    app.generator,
                    app.notes,
                    now,
                    app_id,
                ),
            )
            return app_id
        cur = self.conn.execute(
            "INSERT INTO applications(job_id, company_id, contact_id, channel, status, "
            "recipient_email, subject, body, cover_letter_path, cv_path, tailored_summary, "
            "message_id, thread_refs, generator, sent_at, notes, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                app.job_id,
                app.company_id,
                app.contact_id,
                app.channel,
                app.status,
                app.recipient_email,
                app.subject,
                app.body,
                app.cover_letter_path,
                app.cv_path,
                app.tailored_summary,
                app.message_id,
                app.thread_refs,
                app.generator,
                app.sent_at,
                app.notes,
                app.created_at,
                now,
            ),
        )
        return int(cur.lastrowid or 0)

    def get_application(self, app_id: int) -> Application | None:
        row = self.one("SELECT * FROM applications WHERE id = ?", (app_id,))
        return Application.from_row(row) if row else None

    def get_application_for_job(self, job_id: int) -> Application | None:
        row = self.one("SELECT * FROM applications WHERE job_id = ?", (job_id,))
        return Application.from_row(row) if row else None

    def list_applications(
        self, *, status: str | None = None, limit: int = 200, offset: int = 0
    ) -> list[Application]:
        if status:
            rows = self.query(
                "SELECT * FROM applications WHERE status = ? ORDER BY updated_at DESC "
                "LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
        else:
            rows = self.query(
                "SELECT * FROM applications ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [Application.from_row(r) for r in rows]

    def set_application_status(self, app_id: int, status: str | ApplicationStatus, **extra: Any) -> None:
        assignments = ["status = ?", "updated_at = ?"]
        params: list[Any] = [str(status), utcnow()]
        for key, value in extra.items():
            assignments.append(f"{key} = ?")
            params.append(value)
        params.append(app_id)
        self.conn.execute(
            f"UPDATE applications SET {', '.join(assignments)} WHERE id = ?", tuple(params)
        )

    def sent_count_since(self, iso_timestamp: str) -> int:
        return int(
            self.scalar(
                "SELECT COUNT(*) FROM applications WHERE status IN ('sent','replied','interview',"
                "'offer','rejected','ghosted') AND sent_at >= ?",
                (iso_timestamp,),
            )
            or 0
        )

    def has_contacted_company(self, company_id: int, within_days: int) -> bool:
        row = self.one(
            "SELECT 1 FROM applications WHERE company_id = ? AND sent_at <> '' "
            "AND julianday('now') - julianday(sent_at) < ? LIMIT 1",
            (company_id, within_days),
        )
        return row is not None

    # --------------------------------------------------------------- followups

    def schedule_followup(self, application_id: int, sequence_no: int, due_at: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO followups(application_id, sequence_no, due_at) VALUES(?,?,?) "
            "ON CONFLICT(application_id, sequence_no) DO UPDATE SET due_at=excluded.due_at",
            (application_id, sequence_no, due_at),
        )
        return int(cur.lastrowid or 0)

    def due_followups(self, now_iso: str, limit: int = 25) -> list[sqlite3.Row]:
        return self.query(
            "SELECT f.*, a.status AS app_status FROM followups f "
            "JOIN applications a ON a.id = f.application_id "
            "WHERE f.status = 'pending' AND f.due_at <= ? AND a.status = 'sent' "
            "ORDER BY f.due_at ASC LIMIT ?",
            (now_iso, limit),
        )

    def mark_followup_sent(self, followup_id: int, message_id: str) -> None:
        self.conn.execute(
            "UPDATE followups SET status='sent', sent_at=?, message_id=? WHERE id=?",
            (utcnow(), message_id, followup_id),
        )

    def cancel_followups(self, application_id: int) -> None:
        self.conn.execute(
            "UPDATE followups SET status='cancelled' WHERE application_id=? AND status='pending'",
            (application_id,),
        )

    # ----------------------------------------------------------------- replies

    def record_reply(self, reply: Reply) -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO replies(application_id, from_addr, subject, snippet, "
            "classification, received_at, uid, message_id) VALUES(?,?,?,?,?,?,?,?)",
            (
                reply.application_id,
                reply.from_addr,
                reply.subject,
                reply.snippet,
                reply.classification,
                reply.received_at,
                reply.uid,
                reply.message_id,
            ),
        )
        return int(cur.lastrowid or 0)

    def replies_awaiting_response(self, limit: int = 20) -> list[Reply]:
        """Human replies that deserve an answer and have not had one drafted."""
        rows = self.query(
            "SELECT * FROM replies WHERE classification IN ('interested', 'offer', 'other') "
            "AND draft_status IN ('none', '') AND responded_at = '' "
            "ORDER BY received_at DESC LIMIT ?",
            (limit,),
        )
        return [Reply.from_row(r) for r in rows]

    def replies_with_drafts(self, status: str = "draft", limit: int = 20) -> list[Reply]:
        rows = self.query(
            "SELECT * FROM replies WHERE draft_status = ? ORDER BY received_at DESC LIMIT ?",
            (status, limit),
        )
        return [Reply.from_row(r) for r in rows]

    def save_reply_draft(
        self, reply_id: int, subject: str, body: str, generator: str, status: str = "draft"
    ) -> None:
        self.conn.execute(
            "UPDATE replies SET draft_subject=?, draft_body=?, draft_generator=?, "
            "draft_status=? WHERE id=?",
            (subject, body, generator, status, reply_id),
        )

    def mark_reply_responded(self, reply_id: int) -> None:
        self.conn.execute(
            "UPDATE replies SET draft_status='sent', responded_at=? WHERE id=?",
            (utcnow(), reply_id),
        )

    def get_reply(self, reply_id: int) -> Reply | None:
        row = self.one("SELECT * FROM replies WHERE id = ?", (reply_id,))
        return Reply.from_row(row) if row else None

    def list_replies(self, limit: int = 100) -> list[Reply]:
        rows = self.query("SELECT * FROM replies ORDER BY received_at DESC LIMIT ?", (limit,))
        return [Reply.from_row(r) for r in rows]

    def find_application_by_recipient(self, email: str) -> Application | None:
        row = self.one(
            "SELECT * FROM applications WHERE lower(recipient_email) = lower(?) "
            "ORDER BY sent_at DESC LIMIT 1",
            (email,),
        )
        return Application.from_row(row) if row else None

    # ------------------------------------------------------------ suppressions

    def add_suppression(self, pattern: str, reason: str = "") -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO suppressions(pattern, reason, created_at) VALUES(?,?,?)",
            (pattern.lower().strip(), reason, utcnow()),
        )

    def suppressions(self) -> list[str]:
        return [r["pattern"] for r in self.query("SELECT pattern FROM suppressions")]

    def is_suppressed(self, email: str) -> bool:
        target = email.lower().strip()
        if not target:
            return True
        for pattern in self.suppressions():
            if pattern.startswith("@") and target.endswith(pattern):
                return True
            if pattern == target:
                return True
        return False

    # ------------------------------------------------------------------ events

    def log_event(self, event: Event) -> int:
        cur = self.conn.execute(
            "INSERT INTO events(type, message, job_id, application_id, payload, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                event.type,
                event.message,
                event.job_id,
                event.application_id,
                json.dumps(event.payload),
                event.created_at,
            ),
        )
        return int(cur.lastrowid or 0)

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d.get("payload") or "{}")
            out.append(d)
        return out

    # --------------------------------------------------------------- analytics

    def funnel(self) -> dict[str, Any]:
        job_counts = {
            r["status"]: r["n"]
            for r in self.query("SELECT status, COUNT(*) n FROM jobs GROUP BY status")
        }
        app_counts = {
            r["status"]: r["n"]
            for r in self.query("SELECT status, COUNT(*) n FROM applications GROUP BY status")
        }
        sent = sum(
            app_counts.get(s, 0)
            for s in ("sent", "replied", "interview", "offer", "rejected", "ghosted")
        )
        replied = sum(
            app_counts.get(s, 0) for s in ("replied", "interview", "offer", "rejected")
        )
        positive = app_counts.get("interview", 0) + app_counts.get("offer", 0)
        return {
            "jobs_total": int(self.scalar("SELECT COUNT(*) FROM jobs") or 0),
            "companies_total": int(self.scalar("SELECT COUNT(*) FROM companies") or 0),
            "contacts_total": int(self.scalar("SELECT COUNT(*) FROM contacts") or 0),
            "jobs_by_status": job_counts,
            "applications_by_status": app_counts,
            "sent": sent,
            "replied": replied,
            "positive": positive,
            "reply_rate": round(replied / sent, 4) if sent else 0.0,
            "interview_rate": round(positive / sent, 4) if sent else 0.0,
            "avg_score": round(float(self.scalar("SELECT AVG(score) FROM jobs") or 0), 2),
            "followups_pending": int(
                self.scalar("SELECT COUNT(*) FROM followups WHERE status='pending'") or 0
            ),
        }

    def sends_by_day(self, days: int = 30) -> list[dict[str, Any]]:
        rows = self.query(
            "SELECT substr(sent_at, 1, 10) AS day, COUNT(*) AS n FROM applications "
            "WHERE sent_at <> '' AND julianday('now') - julianday(sent_at) <= ? "
            "GROUP BY day ORDER BY day",
            (days,),
        )
        return [dict(r) for r in rows]
