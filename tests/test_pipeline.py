"""End to end behaviour of the database, drafting and the send guardrails."""

import tempfile
import unittest
from pathlib import Path

from jobseeker.config import Settings
from jobseeker.models import Application, ApplicationStatus, Company, Job, JobStatus
from jobseeker.pipeline import Pipeline

FRONTEND_JD = (
    "You will build interfaces in React and TypeScript with Tailwind CSS. "
    "You will own CI/CD deployments and write tests with Vitest. "
    "This role is fully remote and open to candidates anywhere. " * 6
)


class PipelineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.settings = Settings(
            profile_path="data/profile.example.json",
            boards_path="data/boards.json",
            db_path=str(root / "test.db"),
            letters_dir=str(root / "letters"),
            cv_dir=str(root / "cv"),
            writer="template",
        )
        self.pipeline = Pipeline(self.settings)

    def tearDown(self):
        self.tmp.cleanup()

    def _seed_job(self, **overrides) -> Job:
        defaults = dict(
            title="Frontend Engineer",
            company_name="Acme Systems",
            source="test",
            external_id="acme-1",
            description=FRONTEND_JD,
            location="Remote",
            remote=1,
            posted_at="2026-08-20T00:00:00Z",
        )
        defaults.update(overrides)
        job = Job(**defaults)
        job.company_id = self.pipeline.db.upsert_company(Company(name=job.company_name))
        job_id, _ = self.pipeline.db.upsert_job(job)
        stored = self.pipeline.db.get_job(job_id)
        assert stored is not None
        return stored


class TestPersistence(PipelineTestCase):
    def test_jobs_are_deduplicated_by_source_and_id(self):
        self._seed_job()
        _, was_new = self.pipeline.db.upsert_job(
            Job(title="Frontend Engineer", company_name="Acme Systems", source="test", external_id="acme-1")
        )
        self.assertFalse(was_new)
        self.assertEqual(len(self.pipeline.db.list_jobs()), 1)

    def test_scoring_shortlists_a_good_job(self):
        job = self._seed_job()
        score = self.pipeline.score_one(job)
        self.assertGreater(score, 60)
        self.assertEqual(self.pipeline.db.get_job(int(job.id)).status, JobStatus.SHORTLISTED)


class TestDrafting(PipelineTestCase):
    def test_drafting_produces_documents_and_clean_copy(self):
        job = self._seed_job()
        self.pipeline.score_one(job)
        application = self.pipeline.draft_one(self.pipeline.db.get_job(int(job.id)))

        self.assertTrue(Path(application.cover_letter_path).exists())
        self.assertTrue(Path(application.cv_path).exists())
        self.assertIn("Acme Systems", application.body)
        for dash in "—–":
            self.assertNotIn(dash, application.body)
            self.assertNotIn(dash, application.subject)

    def test_a_job_without_a_contact_routes_to_the_portal(self):
        job = self._seed_job()
        self.pipeline.score_one(job)
        application = self.pipeline.draft_one(self.pipeline.db.get_job(int(job.id)))
        self.assertEqual(application.channel, "portal")


class TestSendGuardrails(PipelineTestCase):
    def _approved_application(self) -> tuple[Application, Job]:
        job = self._seed_job()
        self.pipeline.score_one(job)
        job = self.pipeline.db.get_job(int(job.id))
        application = self.pipeline.draft_one(job)
        application.recipient_email = "careers@acme.test"
        application.channel = "email"
        application.status = ApplicationStatus.APPROVED
        self.pipeline.db.upsert_application(application)
        stored = self.pipeline.db.get_application(int(application.id))
        return stored, job

    def test_a_draft_is_never_sent(self):
        job = self._seed_job()
        self.pipeline.score_one(job)
        application = self.pipeline.draft_one(self.pipeline.db.get_job(int(job.id)))
        reason = self.pipeline._send_guardrails(application, job)
        self.assertIn("not approved", reason)

    def test_suppressed_recipients_are_blocked(self):
        application, job = self._approved_application()
        self.pipeline.db.add_suppression("@acme.test", "asked not to be contacted")
        self.assertIn("suppression", self.pipeline._send_guardrails(application, job))

    def test_a_low_score_is_blocked_from_sending(self):
        application, job = self._approved_application()
        self.pipeline.db.update_job_score(int(job.id), 20.0, {})
        job = self.pipeline.db.get_job(int(job.id))
        self.assertIn("below the send threshold", self.pipeline._send_guardrails(application, job))

    def test_send_defaults_to_a_dry_run(self):
        self._approved_application()
        result = self.pipeline.send(dry_run=True)
        self.assertEqual(result.counts["sent"], 0)
        self.assertTrue(
            any(item["status"] in {"dry_run", "blocked"} for item in result.items)
        )
        # Nothing may be marked sent by a dry run.
        self.assertEqual(self.pipeline.db.funnel()["sent"], 0)


class TestFollowups(PipelineTestCase):
    def test_followups_are_scheduled_and_cancelled(self):
        job = self._seed_job()
        self.pipeline.score_one(job)
        application = self.pipeline.draft_one(self.pipeline.db.get_job(int(job.id)))
        due = self.pipeline.followups.schedule_for(int(application.id), "2026-01-01T00:00:00+00:00")
        self.assertEqual(len(due), len(self.pipeline.followups.steps))

        self.pipeline.followups.cancel_for(int(application.id))
        pending = self.pipeline.db.scalar(
            "SELECT COUNT(*) FROM followups WHERE status = 'pending'"
        )
        self.assertEqual(pending, 0)

    def test_followup_copy_is_clean_and_offers_an_exit(self):
        job = self._seed_job()
        self.pipeline.score_one(job)
        application = self.pipeline.draft_one(self.pipeline.db.get_job(int(job.id)))
        message = self.pipeline.followups.compose(job, application, 1)
        self.assertNotIn("—", message.body)
        self.assertIn("stop chasing", message.body)


if __name__ == "__main__":
    unittest.main()


class TestRedraftSafety(PipelineTestCase):
    """Rewriting a letter must not undo decisions already made about it."""

    def _drafted(self):
        job = self._seed_job()
        self.pipeline.score_one(job)
        return self.pipeline.draft_one(self.pipeline.db.get_job(int(job.id))), job

    def test_an_approval_survives_a_redraft(self):
        application, job = self._drafted()
        self.pipeline.db.set_application_status(int(application.id), ApplicationStatus.APPROVED)

        self.pipeline.draft_one(self.pipeline.db.get_job(int(job.id)))

        after = self.pipeline.db.get_application(int(application.id))
        self.assertEqual(after.status, ApplicationStatus.APPROVED)

    def test_a_sent_application_is_never_reset(self):
        application, job = self._drafted()
        self.pipeline.db.set_application_status(
            int(application.id), ApplicationStatus.SENT, sent_at="2026-08-23T10:00:00+00:00"
        )

        self.pipeline.draft_one(self.pipeline.db.get_job(int(job.id)))

        after = self.pipeline.db.get_application(int(application.id))
        self.assertEqual(after.status, ApplicationStatus.SENT)
        self.assertTrue(after.sent_at)

    def test_a_plain_draft_can_still_be_rewritten(self):
        application, job = self._drafted()
        self.pipeline.draft_one(self.pipeline.db.get_job(int(job.id)))
        after = self.pipeline.db.get_application(int(application.id))
        self.assertEqual(after.status, ApplicationStatus.DRAFT)
