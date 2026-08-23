"""The engine. Every stage of the funnel, in one place.

    discover  ->  score  ->  draft  ->  approve  ->  send  ->  follow up  ->  sync replies

Each stage is independent and idempotent: running it twice does not duplicate
work, and a stage can be run on its own from the CLI, the API or a cron job.
Approval sits deliberately between drafting and sending, because an automated
system that can email strangers in your name without a human ever looking is a
system that will eventually embarrass you.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from . import sources as source_pkg
from .config import Settings
from .db import Database
from .documents import build_cover_letter, build_cv
from .enrich import find_contacts
from .llm import get_writer
from .models import (
    Application,
    ApplicationStatus,
    Channel,
    Company,
    Event,
    Job,
    JobStatus,
    utcnow,
)
from .outreach import FollowupPlanner, InboxReader, Mailer, classify_reply
from .outreach import digest as digest_module
from .outreach.inbox import STATUS_FOR_CLASSIFICATION
from .outreach.responder import auto_send_allowed, draft_reply
from .persona import Persona
from .scoring import score_job
from .sources.base import dedupe, get as get_source
from .util import env, log
from .util.style import sanitise


@dataclass(slots=True)
class StageResult:
    stage: str
    counts: dict[str, int] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "counts": self.counts,
            "messages": self.messages,
            "items": self.items,
        }

    def summary(self) -> str:
        parts = ", ".join(f"{value} {key}" for key, value in self.counts.items())
        return f"{self.stage}: {parts or 'nothing to do'}"


class Pipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        self.persona = Persona.load(self.settings.profile_path)
        self.db = Database(self.settings.db_path)
        self.mailer = Mailer(sender_name=self.persona.name)
        self.followups = FollowupPlanner(self.db, self.persona)

    # ------------------------------------------------------------- discover

    def discover(
        self,
        source_names: Iterable[str] | None = None,
        *,
        keywords: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> StageResult:
        """Pull open roles from every configured source and store the new ones."""
        result = StageResult("discover")
        boards = self.settings.boards()
        names = list(source_names or self.settings.default_sources)
        keywords = keywords or self.persona.targeting.get("roles", [])[:6]

        collected: list[Job] = []
        for name in names:
            try:
                fetch = get_source(name)
            except Exception as exc:  # noqa: BLE001
                result.messages.append(str(exc))
                continue

            kwargs: dict[str, Any] = dict(extra or {})
            if name in {"greenhouse", "ashby"}:
                kwargs.setdefault("boards", boards.get(name, []))
            elif name == "lever":
                kwargs.setdefault("companies", boards.get("lever", []))
            elif name == "workable":
                kwargs.setdefault("accounts", boards.get("workable", []))
            elif name in {"arbeitnow", "remoteok"}:
                kwargs.setdefault("keywords", keywords)

            try:
                found = fetch(**kwargs)
            except Exception as exc:  # noqa: BLE001
                log.warn(f"source '{name}' failed: {exc}")
                result.messages.append(f"{name} failed: {exc}")
                continue
            result.counts[name] = len(found)
            collected.extend(found)

        new_count = 0
        for job in dedupe(collected):
            if not job.title or not job.company_name:
                continue
            company_id = self.db.upsert_company(
                Company(name=job.company_name, source=job.source)
            )
            job.company_id = company_id
            _, was_new = self.db.upsert_job(job)
            new_count += int(was_new)

        result.counts["fetched"] = len(collected)
        result.counts["new"] = new_count
        self.db.log_event(
            Event(type="discover", message=result.summary(), payload=result.counts)
        )
        return result

    def add_job_from_url(self, url: str, company: str = "", title: str = "") -> Job | None:
        """Ingest one posting the applicant found herself."""
        fetch = get_source("url")
        jobs = fetch(url=url, company=company, title=title)
        if not jobs:
            return None
        job = jobs[0]
        job.company_id = self.db.upsert_company(Company(name=job.company_name, source="manual"))
        job_id, _ = self.db.upsert_job(job)
        stored = self.db.get_job(job_id)
        if stored:
            self.score_one(stored)
        return self.db.get_job(job_id)

    # ---------------------------------------------------------------- score

    def score_one(self, job: Job) -> float:
        outcome = score_job(
            self.persona,
            title=job.title,
            description=job.description,
            location=job.location,
            remote=job.remote,
            posted_at=job.posted_at,
            company_name=job.company_name,
        )
        self.db.update_job_score(int(job.id or 0), outcome.score, outcome.to_dict())
        if outcome.blocked:
            self.db.set_job_status(int(job.id or 0), JobStatus.REJECTED_BY_ME)
        elif outcome.score >= self.settings.min_score_to_draft:
            self.db.set_job_status(int(job.id or 0), JobStatus.SHORTLISTED)
        return outcome.score

    def score_all(self, rescore: bool = False) -> StageResult:
        """Score everything that has not been scored, or everything if asked."""
        result = StageResult("score")
        statuses = None if rescore else JobStatus.NEW
        jobs = self.db.list_jobs(status=statuses, limit=5000, order="id ASC")
        shortlisted = blocked = 0
        for job in jobs:
            score = self.score_one(job)
            if score == 0:
                blocked += 1
            elif score >= self.settings.min_score_to_draft:
                shortlisted += 1
        result.counts = {
            "scored": len(jobs),
            "shortlisted": shortlisted,
            "blocked": blocked,
        }
        self.db.log_event(Event(type="score", message=result.summary(), payload=result.counts))
        return result

    # ---------------------------------------------------------------- draft

    def draft_one(self, job: Job, *, writer_name: str | None = None) -> Application:
        """Generate the letter, the tailored CV and the email for one job."""
        writer = get_writer(writer_name or self.settings.writer)
        contact = (
            self.db.best_contact_for_company(int(job.company_id))
            if job.company_id
            else None
        )
        matched = [s.name for s in self.persona.matched_skills(job.description or job.title)]
        draft = writer.write(
            self.persona,
            job,
            contact_name=contact.name if contact and contact.name else "",
            matched_skills=matched,
        )

        letter_path = build_cover_letter(
            self.persona,
            job,
            draft,
            output_dir=self.settings.letters_dir,
            recipient_name=contact.name if contact and contact.name else "",
        )
        cv_path = self._cv_for(job)

        # An ATS application still needs a human to press submit on the portal,
        # so the channel is recorded rather than assumed to be email.
        channel = Channel.EMAIL if contact else Channel.PORTAL
        application = Application(
            job_id=int(job.id or 0),
            company_id=job.company_id,
            contact_id=contact.id if contact else None,
            channel=channel,
            status=ApplicationStatus.DRAFT,
            recipient_email=contact.email if contact else "",
            subject=draft.subject,
            body=draft.email_body,
            cover_letter_path=str(letter_path),
            cv_path=str(cv_path),
            tailored_summary=draft.tailored_summary,
            generator=draft.generator,
            notes="; ".join(draft.style_notes),
        )
        app_id = self.db.upsert_application(application)
        application.id = app_id
        self.db.set_job_status(int(job.id or 0), JobStatus.DRAFTED)
        self.db.log_event(
            Event(
                type="draft",
                message=f"drafted {job.title} at {job.company_name}",
                job_id=job.id,
                application_id=app_id,
                payload={"generator": draft.generator, "tokens": draft.tokens_used},
            )
        )
        return application

    def _cv_for(self, job: Job) -> str:
        """Which CV to attach.

        Her own PDF is the default. It is the document she wrote, designed and
        stands behind, and no generated file should quietly replace it. The
        generated one reorders her skills for a specific posting, which is
        useful, so it stays available through CV_MODE=tailored.

        If the master file is missing the generated CV is used rather than
        sending an application with no CV at all.
        """
        mode = (env.get("CV_MODE", "master") or "master").strip().lower()
        master = Path(self.persona.cv_path or "")

        if mode == "master":
            if master.exists():
                return str(master)
            log.warn(
                f"CV_MODE is master but {master} is missing, using the generated CV instead"
            )
        return str(build_cv(self.persona, job, output_dir=self.settings.cv_dir))

    def draft(self, limit: int = 10, min_score: float | None = None) -> StageResult:
        result = StageResult("draft")
        threshold = min_score if min_score is not None else self.settings.min_score_to_draft
        pool = [
            job
            for job in self.db.list_jobs(min_score=threshold, limit=limit * 8)
            if job.status in {JobStatus.SCORED, JobStatus.SHORTLISTED}
            and not self.db.get_application_for_job(int(job.id or 0))
        ]

        # A job with a contact is one the engine can carry all the way. A portal
        # job needs a person no matter how well it scores, so when slots are
        # limited the reachable ones go first. Score still orders within each
        # group, so this changes what gets done first, not what counts as good.
        def priority(job: Job) -> tuple[int, float]:
            reachable = bool(
                job.company_id and self.db.best_contact_for_company(int(job.company_id))
            )
            return (1 if reachable else 0, job.score)

        candidates = sorted(pool, key=priority, reverse=True)[:limit]

        for job in candidates:
            try:
                application = self.draft_one(job)
            except Exception as exc:  # noqa: BLE001
                log.warn(f"drafting failed for {job.company_name}: {exc}")
                result.messages.append(f"{job.company_name}: {exc}")
                continue
            result.items.append(
                {
                    "application_id": application.id,
                    "job_id": job.id,
                    "company": job.company_name,
                    "title": job.title,
                    "score": job.score,
                    "channel": application.channel,
                    "generator": application.generator,
                }
            )
        result.counts = {"drafted": len(result.items), "considered": len(candidates)}
        return result

    # -------------------------------------------------------------- approve

    def approve(self, application_ids: Iterable[int]) -> StageResult:
        """Mark drafts as approved. This is the human in the loop."""
        result = StageResult("approve")
        approved = 0
        for app_id in application_ids:
            application = self.db.get_application(int(app_id))
            if not application:
                result.messages.append(f"application {app_id} not found")
                continue
            if application.status not in {ApplicationStatus.DRAFT, ApplicationStatus.FAILED}:
                result.messages.append(
                    f"application {app_id} is '{application.status}', only drafts can be approved"
                )
                continue
            self.db.set_application_status(int(app_id), ApplicationStatus.APPROVED)
            approved += 1
        result.counts = {"approved": approved}
        return result

    def auto_approve(self) -> StageResult:
        """Approve high scoring drafts without a person, when that is switched on.

        This is the difference between a system that finds work for you and one
        that applies for you. It is off by default, and even when on it only
        touches drafts that clear a higher bar than the normal send threshold,
        so the automatic path is always more conservative than the manual one.
        """
        result = StageResult("auto_approve")
        threshold = env.get_int("AUTO_APPROVE_SCORE", 0)
        if not threshold:
            result.messages.append(
                "AUTO_APPROVE_SCORE is not set, so every application still waits for you."
            )
            result.counts = {"approved": 0}
            return result

        approved = 0
        skipped = 0
        for application in self.db.list_applications(status=ApplicationStatus.DRAFT, limit=200):
            job = self.db.get_job(application.job_id)
            if not job or job.score < threshold:
                skipped += 1
                continue
            # A draft the style guard was unhappy with never goes out unread.
            if application.notes:
                skipped += 1
                result.messages.append(
                    f"{job.company_name}: held back because the draft needs a look ({application.notes})"
                )
                continue
            self.db.set_application_status(int(application.id or 0), ApplicationStatus.APPROVED)
            self.db.log_event(
                Event(
                    type="auto_approved",
                    message=f"{job.title} at {job.company_name} (score {job.score})",
                    job_id=job.id,
                    application_id=application.id,
                )
            )
            result.items.append(
                {"company": job.company_name, "title": job.title, "score": job.score,
                 "status": "approved"}
            )
            approved += 1

        result.counts = {"approved": approved, "left_for_you": skipped, "threshold": threshold}
        return result

    # ----------------------------------------------------------------- send

    def _send_guardrails(self, application: Application, job: Job) -> str:
        """Return a blocking reason, or an empty string when the send may proceed."""
        if application.status != ApplicationStatus.APPROVED:
            return f"status is '{application.status}', not approved"
        if application.channel != Channel.EMAIL:
            return "this role applies through a portal, not by email"
        if not application.recipient_email:
            return "no recipient address"
        if self.db.is_suppressed(application.recipient_email):
            return "recipient is on the suppression list"
        if job.score < self.settings.min_score_to_send:
            return f"score {job.score} is below the send threshold {self.settings.min_score_to_send}"
        if application.company_id and self.db.has_contacted_company(
            int(application.company_id), self.settings.per_company_cooldown_days
        ):
            return (
                f"this company was contacted within the last "
                f"{self.settings.per_company_cooldown_days} days"
            )
        for path in (application.cover_letter_path, application.cv_path):
            if path and not Path(path).exists():
                return f"attachment missing on disk: {path}"

        # A domain with no mail route guarantees a bounce, which costs sender
        # reputation and leaves a dead application looking live.
        from .util.dns import address_deliverable

        deliverable, note = address_deliverable(application.recipient_email)
        if not deliverable:
            return note
        if note:
            log.warn(note)
        return ""

    def send(self, limit: int | None = None, *, dry_run: bool = True) -> StageResult:
        """Send approved applications, newest and highest scoring first."""
        result = StageResult("send")
        cap = limit or self.settings.daily_send_cap

        midnight = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat(timespec="seconds")
        already_sent_today = self.db.sent_count_since(midnight)
        remaining = max(0, self.settings.daily_send_cap - already_sent_today)
        if remaining == 0 and not dry_run:
            result.messages.append(
                f"daily cap reached: {already_sent_today} of {self.settings.daily_send_cap} sent today"
            )
            result.counts = {"sent": 0, "blocked": 0, "skipped": 0}
            return result

        approved = self.db.list_applications(status=ApplicationStatus.APPROVED, limit=cap * 3)
        queue: list[tuple[Application, Job]] = []
        for application in approved:
            job = self.db.get_job(application.job_id)
            if not job:
                continue
            queue.append((application, job))
        queue.sort(key=lambda pair: pair[1].score, reverse=True)
        queue = queue[: min(cap, remaining if not dry_run else cap)]

        sent = blocked = failed = 0
        for index, (application, job) in enumerate(queue):
            reason = self._send_guardrails(application, job)
            if reason:
                blocked += 1
                result.items.append(
                    {
                        "application_id": application.id,
                        "company": job.company_name,
                        "status": "blocked",
                        "reason": reason,
                    }
                )
                self.db.log_event(
                    Event(
                        type="send_blocked",
                        message=reason,
                        job_id=job.id,
                        application_id=application.id,
                    )
                )
                continue

            outcome = self.mailer.send(
                to=application.recipient_email,
                subject=sanitise(application.subject),
                body=sanitise(application.body),
                attachments=[
                    p for p in (application.cover_letter_path, application.cv_path) if p
                ],
                dry_run=dry_run,
            )

            if outcome.ok and not outcome.dry_run:
                self.db.set_application_status(
                    int(application.id or 0),
                    ApplicationStatus.SENT,
                    sent_at=outcome.sent_at,
                    message_id=outcome.message_id,
                )
                self.db.set_job_status(int(job.id or 0), JobStatus.APPLIED)
                self.followups.schedule_for(int(application.id or 0), outcome.sent_at)
                sent += 1
                status = "sent"
            elif outcome.ok:
                status = "dry_run"
            else:
                self.db.set_application_status(
                    int(application.id or 0),
                    ApplicationStatus.FAILED,
                    notes=outcome.error,
                )
                failed += 1
                status = "failed"

            result.items.append(
                {
                    "application_id": application.id,
                    "company": job.company_name,
                    "title": job.title,
                    "recipient": application.recipient_email,
                    "status": status,
                    "reason": outcome.error,
                }
            )
            self.db.log_event(
                Event(
                    type=f"send_{status}",
                    message=f"{job.title} at {job.company_name}",
                    job_id=job.id,
                    application_id=application.id,
                    payload={"recipient": application.recipient_email},
                )
            )

            if not dry_run and outcome.ok:
                self.mailer.pace(index, len(queue))

        result.counts = {
            "queued": len(queue),
            "sent": sent,
            "blocked": blocked,
            "failed": failed,
            "sent_today": already_sent_today + sent,
        }
        return result

    # ------------------------------------------------------------ follow up

    def run_followups(self, limit: int = 10, *, dry_run: bool = True) -> StageResult:
        result = StageResult("followup")
        due = self.followups.due(limit=limit)
        sent = failed = 0

        for index, entry in enumerate(due):
            application: Application = entry["application"]
            job: Job = entry["job"]
            message = self.followups.compose(job, application, entry["sequence_no"])

            outcome = self.mailer.send(
                to=application.recipient_email,
                subject=message.subject,
                body=message.body,
                in_reply_to=application.message_id,
                references=application.thread_refs or application.message_id,
                dry_run=dry_run,
            )
            if outcome.ok and not outcome.dry_run:
                self.db.mark_followup_sent(entry["followup_id"], outcome.message_id)
                sent += 1
                status = "sent"
            elif outcome.ok:
                status = "dry_run"
            else:
                failed += 1
                status = "failed"

            result.items.append(
                {
                    "application_id": application.id,
                    "company": job.company_name,
                    "sequence_no": entry["sequence_no"],
                    "status": status,
                    "reason": outcome.error,
                }
            )
            if not dry_run and outcome.ok:
                self.mailer.pace(index, len(due))

        result.counts = {"due": len(due), "sent": sent, "failed": failed}
        return result

    # --------------------------------------------------------- sync replies

    def sync_replies(self, days: int = 14, *, use_llm: bool = True) -> StageResult:
        """Read the inbox, attach replies to applications and update statuses."""
        result = StageResult("replies")
        reader = InboxReader()
        ok, why = reader.ready()
        if not ok:
            result.messages.append(why)
            return result

        try:
            messages = reader.fetch_recent(days=days)
        except Exception as exc:  # noqa: BLE001
            result.messages.append(f"inbox read failed: {exc}")
            return result

        from .models import Reply

        matched = updated = 0
        counts: dict[str, int] = {}
        own_address = (self.mailer.sender_email or "").lower()

        for message in messages:
            if not message.from_addr or message.from_addr == own_address:
                continue
            classification = classify_reply(
                message.subject, message.body, use_llm=use_llm, sender=message.from_addr
            )

            application = reader.match_application(self.db, message)
            if not application and classification == "bounce":
                from .outreach.inbox import bounced_address

                failed = bounced_address(message.body, own_address)
                if failed:
                    application = self.db.find_application_by_recipient(failed)

            if not application:
                continue
            matched += 1
            counts[classification] = counts.get(classification, 0) + 1

            self.db.record_reply(
                Reply(
                    application_id=application.id,
                    from_addr=message.from_addr,
                    subject=message.subject,
                    snippet=message.snippet,
                    classification=classification,
                    uid=f"{message.uid}:{message.from_addr}",
                )
            )

            if classification == "bounce":
                # The address is dead, so nothing should ever go there again.
                self.db.add_suppression(
                    application.recipient_email, "mail to this address bounced"
                )
                log.warn(
                    f"{application.recipient_email} bounced, marked failed and suppressed"
                )

            new_status = STATUS_FOR_CLASSIFICATION.get(classification)
            if new_status and application.status not in {
                ApplicationStatus.OFFER,
                ApplicationStatus.INTERVIEW,
            }:
                self.db.set_application_status(int(application.id or 0), new_status)
                updated += 1
            if classification != "auto_ack":
                # A human answered. Nothing scheduled should still go out.
                self.followups.cancel_for(int(application.id or 0), classification)

        result.counts = {"read": len(messages), "matched": matched, "updated": updated, **counts}
        return result

    # -------------------------------------------------------------- respond

    def respond(self, limit: int = 10, *, dry_run: bool = True) -> StageResult:
        """Draft, and optionally send, answers to the people who replied."""
        result = StageResult("respond")
        pending = self.db.replies_awaiting_response(limit=limit)

        drafted = sent = held = 0
        for reply in pending:
            application = (
                self.db.get_application(int(reply.application_id))
                if reply.application_id
                else None
            )
            job = self.db.get_job(application.job_id) if application else None

            draft = draft_reply(self.persona, reply, job, application)
            self.db.save_reply_draft(
                int(reply.id or 0), draft.subject, draft.body, draft.generator
            )
            drafted += 1

            allowed, why = auto_send_allowed(draft)
            if not allowed:
                held += 1
                result.items.append(
                    {
                        "company": job.company_name if job else reply.from_addr,
                        "status": "needs you",
                        "reason": why,
                    }
                )
                continue

            outcome = self.mailer.send(
                to=reply.from_addr,
                subject=draft.subject,
                body=draft.body,
                in_reply_to=reply.message_id or (application.message_id if application else ""),
                references=application.thread_refs if application else "",
                dry_run=dry_run,
            )
            if outcome.ok and not outcome.dry_run:
                self.db.mark_reply_responded(int(reply.id or 0))
                sent += 1
                status = "sent"
            elif outcome.ok:
                status = "dry_run"
            else:
                status = "failed"
                result.messages.append(f"{reply.from_addr}: {outcome.error}")

            result.items.append(
                {
                    "company": job.company_name if job else reply.from_addr,
                    "status": status,
                    "reason": "",
                }
            )
            self.db.log_event(
                Event(
                    type=f"reply_{status}",
                    message=f"reply to {reply.from_addr}",
                    application_id=reply.application_id,
                )
            )

        result.counts = {
            "pending": len(pending),
            "drafted": drafted,
            "sent": sent,
            "needs_you": held,
        }
        return result

    # --------------------------------------------------------------- digest

    def send_digest(self, extra: dict[str, Any] | None = None, *, dry_run: bool = True) -> StageResult:
        """Email the applicant a summary of what happened and what needs them."""
        result = StageResult("digest")
        recipient = env.get("DIGEST_TO") or self.persona.identity.get("email", "")
        if not recipient:
            result.messages.append("DIGEST_TO is not set, so there is nowhere to send it")
            return result

        stats = self.stats()
        needs_you = []
        for application in self.db.list_applications(status=ApplicationStatus.DRAFT, limit=8):
            job = self.db.get_job(application.job_id)
            if job:
                needs_you.append(f"{job.title} at {job.company_name} (score {job.score:.0f})")

        detail = {
            "new_replies": len(self.db.list_replies(limit=50)),
            "replies_to_answer": len(self.db.replies_with_drafts("draft", limit=50)),
            "needs_you": needs_you,
            **(extra or {}),
        }

        subject, body = digest_module.compose(stats, detail, self.persona.first_name)
        outcome = self.mailer.send(to=recipient, subject=subject, body=body, dry_run=dry_run)
        result.counts = {"sent": 1 if outcome.ok and not outcome.dry_run else 0}
        if not outcome.ok:
            result.messages.append(outcome.error)
        result.items.append({"company": recipient, "status": "sent" if outcome.ok else "failed"})
        return result

    # ------------------------------------------------------------- prospect

    def prospect(self, query: str, limit: int = 10, *, enrich: bool = True) -> StageResult:
        """Cold outreach path: find companies, find a human, queue a speculative role."""
        from .sources.exa import search_companies

        result = StageResult("prospect")
        companies = search_companies(query, limit=limit)
        target_role = (self.persona.targeting.get("roles") or ["Software Engineer"])[0]
        added = enriched = 0

        for company in companies:
            company_id = self.db.upsert_company(company)
            if enrich:
                contacts = find_contacts(
                    company_id, domain=company.domain, website=company.website, limit=3
                )
                for contact in contacts:
                    self.db.upsert_contact(contact)
                enriched += 1 if contacts else 0

            job = Job(
                title=f"{target_role} (speculative)",
                company_name=company.name,
                source="speculative",
                external_id=company.domain or company.name,
                url=company.website,
                location=self.persona.identity.get("location", ""),
                remote=1,
                description=(
                    f"Speculative application to {company.name}. "
                    f"What the company says about itself: {company.notes}"
                ),
                company_id=company_id,
            )
            _, was_new = self.db.upsert_job(job)
            added += int(was_new)

        result.counts = {
            "companies": len(companies),
            "new_targets": added,
            "with_contacts": enriched,
        }
        return result

    def prospect_local(self, limit: int = 12, *, group: str = "") -> StageResult:
        """Speculative outreach to companies from the seed list, with no paid key.

        Most hiring in Ghana never reaches a public job board, and the roles that
        do are almost all portal applications the engine cannot submit. This is
        the path that can genuinely run unattended: resolve the company's own
        domain, read the hiring address it publishes, and queue a speculative
        application to a real inbox.
        """
        import json as json_module

        from .enrich.careers import find_contacts_free

        result = StageResult("prospect_local")
        path = Path(self.settings.boards_path).parent / "companies.json"
        if not path.exists():
            result.messages.append(f"no seed list at {path}")
            return result

        seeds = json_module.loads(path.read_text(encoding="utf-8"))
        groups = [group] if group else [k for k in seeds if not k.startswith("_")]
        entries = [entry for key in groups for entry in seeds.get(key, [])]

        target_role = (self.persona.targeting.get("roles") or ["Software Engineer"])[0]
        added = with_contacts = 0

        for entry in entries[:limit]:
            name = entry.get("name", "").strip()
            if not name:
                continue

            existing = self.db.find_company_by_name(name)
            company_id = self.db.upsert_company(
                Company(
                    name=name,
                    domain=entry.get("domain", ""),
                    website=f"https://{entry['domain']}" if entry.get("domain") else "",
                    industry=entry.get("industry", ""),
                    source="seed",
                    location=entry.get("location", "Ghana"),
                )
            )

            contacts = []
            if not (existing and self.db.best_contact_for_company(company_id)):
                contacts = find_contacts_free(
                    company_id, name, entry.get("domain", ""), limit=2
                )
                for contact in contacts:
                    self.db.upsert_contact(contact)
            if contacts or self.db.best_contact_for_company(company_id):
                with_contacts += 1

            job = Job(
                title=f"{target_role} (speculative)",
                company_name=name,
                source="speculative",
                external_id=entry.get("domain") or name,
                url=f"https://{entry['domain']}" if entry.get("domain") else "",
                location=entry.get("location", "Ghana"),
                remote=0,
                description=(
                    f"Speculative application to {name}, a {entry.get('industry', 'technology')} "
                    f"company. This is an approach made directly rather than an answer to a "
                    f"posted role, so the letter has to argue for itself. "
                    f"Relevant skills: {', '.join(self.persona.skill_names(('core',))[:8])}."
                ),
                company_id=company_id,
            )
            _, was_new = self.db.upsert_job(job)
            added += int(was_new)
            if was_new:
                stored = self.db.get_job(
                    int(self.db.one(
                        "SELECT id FROM jobs WHERE source='speculative' AND external_id=?",
                        (job.external_id,),
                    )["id"])
                )
                if stored:
                    self.score_one(stored)

            result.items.append(
                {
                    "company": name,
                    "status": "reachable" if contacts else "no public address",
                    "reason": contacts[0].email if contacts else "",
                }
            )

        result.counts = {
            "companies": len(entries[:limit]),
            "new_targets": added,
            "reachable": with_contacts,
        }
        self.db.log_event(
            Event(type="prospect_local", message=result.summary(), payload=result.counts)
        )
        return result

    def enrich_company(self, company_id: int) -> StageResult:
        result = StageResult("enrich")
        company = self.db.get_company(company_id)
        if not company:
            result.messages.append(f"company {company_id} not found")
            return result
        contacts = find_contacts(
            company_id, domain=company.domain, website=company.website, limit=5
        )
        for contact in contacts:
            self.db.upsert_contact(contact)
        result.counts = {"contacts": len(contacts)}
        result.items = [
            {"email": c.email, "name": c.name, "title": c.title, "source": c.source}
            for c in contacts
        ]
        return result

    # ---------------------------------------------------------------- daily

    def run_daily(self, *, dry_run: bool = True) -> list[StageResult]:
        """One full cycle, safe to run from cron.

        In dry run nothing leaves the machine: it discovers, scores, drafts and
        reads the inbox, and every send is simulated. With `dry_run=False` it
        becomes the autonomous loop: apply, chase, answer, and report back.
        """
        discovered = self.discover()
        scored = self.score_all()
        drafted = self.draft(limit=self.settings.daily_send_cap)
        replies = self.sync_replies()
        approved = self.auto_approve()

        stages = [discovered, scored, drafted, replies, approved]
        stages.append(self.send(dry_run=dry_run))
        stages.append(self.run_followups(dry_run=dry_run))
        stages.append(self.respond(dry_run=dry_run))

        stages.append(
            self.send_digest(
                extra={
                    "discovered": discovered.counts.get("new", 0),
                    "drafted": drafted.counts.get("drafted", 0),
                    "problems": [m for stage in stages for m in stage.messages][:5],
                },
                dry_run=dry_run,
            )
        )
        return stages

    # ------------------------------------------------------------ reporting

    def stats(self) -> dict[str, Any]:
        funnel = self.db.funnel()
        funnel["sends_by_day"] = self.db.sends_by_day(30)
        funnel["send_enabled"] = self.mailer.send_enabled()
        funnel["writer"] = get_writer(self.settings.writer).name
        funnel["daily_cap"] = self.settings.daily_send_cap
        midnight = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat(timespec="seconds")
        funnel["sent_today"] = self.db.sent_count_since(midnight)
        funnel["next_followup"] = self.db.scalar(
            "SELECT MIN(due_at) FROM followups WHERE status = 'pending'"
        )
        return funnel
