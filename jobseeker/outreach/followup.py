"""Follow up sequencing.

Two follow ups, then stop. The first is a short nudge, the second offers to
close the loop and step away. Both go into the original thread using the stored
Message-ID, and any reply cancels everything still pending.

Silence is an answer. The sequence is deliberately short because a third chase
email costs more goodwill than it can ever recover.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..db import Database
from ..models import Application, ApplicationStatus, Job, utcnow
from ..persona import Persona
from ..util import env, log
from ..util.style import sanitise

DEFAULT_STEPS = (6, 14)   # days after the original send


@dataclass(slots=True)
class FollowupMessage:
    subject: str
    body: str
    sequence_no: int


class FollowupPlanner:
    def __init__(self, db: Database, persona: Persona) -> None:
        self.db = db
        self.persona = persona
        self.steps = self._configured_steps()

    @staticmethod
    def _configured_steps() -> tuple[int, ...]:
        raw = env.get_list("FOLLOWUP_DAYS", [str(d) for d in DEFAULT_STEPS])
        try:
            steps = tuple(sorted({int(value) for value in raw}))
        except ValueError:
            log.warn("FOLLOWUP_DAYS must be a comma separated list of whole days")
            return DEFAULT_STEPS
        return steps or DEFAULT_STEPS

    def schedule_for(self, application_id: int, sent_at: str = "") -> list[str]:
        """Queue every follow up for one application. Returns the due dates."""
        base = _parse(sent_at) or datetime.now(timezone.utc)
        due_dates = []
        for index, offset in enumerate(self.steps, start=1):
            due = (base + timedelta(days=offset)).isoformat(timespec="seconds")
            self.db.schedule_followup(application_id, index, due)
            due_dates.append(due)
        return due_dates

    def compose(
        self, job: Job, application: Application, sequence_no: int
    ) -> FollowupMessage:
        """Write the nudge. Short, no guilt, always with an exit."""
        subject = f"Re: {application.subject}" if application.subject else f"Re: {job.title}"
        role_line = f"the {job.title} role"
        link = self.persona.identity.get("website", "")

        if sequence_no == 1:
            body = (
                f"Hello again,\n\n"
                f"I applied for {role_line} at {job.company_name} last week and wanted to "
                f"put my name back in front of you in case the thread got buried.\n\n"
                f"If it helps, my work is at {link} and I am happy to walk through anything "
                f"in the application on a short call.\n\n"
                f"If the role has been filled or I am not the right fit, please say so and "
                f"I will stop chasing.\n\n"
                f"Best regards,\n{self.persona.signature()}"
            )
        else:
            body = (
                f"Hello,\n\n"
                f"This is my last note about {role_line} at {job.company_name}. I know how "
                f"full an inbox gets.\n\n"
                f"If there is still interest I would welcome a conversation. If not, I would "
                f"be glad to be considered for something later, and I will leave it there.\n\n"
                f"Best regards,\n{self.persona.signature()}"
            )

        return FollowupMessage(
            subject=sanitise(subject), body=sanitise(body), sequence_no=sequence_no
        )

    def due(self, limit: int = 10) -> list[dict]:
        """Follow ups that are ready to go right now."""
        rows = self.db.due_followups(utcnow(), limit=limit)
        pending = []
        for row in rows:
            application = self.db.get_application(int(row["application_id"]))
            if not application or application.status != ApplicationStatus.SENT:
                continue
            job = self.db.get_job(application.job_id)
            if not job:
                continue
            pending.append(
                {
                    "followup_id": int(row["id"]),
                    "sequence_no": int(row["sequence_no"]),
                    "due_at": row["due_at"],
                    "application": application,
                    "job": job,
                }
            )
        return pending

    def cancel_for(self, application_id: int, reason: str = "reply received") -> None:
        self.db.cancel_followups(application_id)
        log.dim(f"cancelled pending follow ups for application {application_id}: {reason}")


def _parse(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
