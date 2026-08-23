"""The autonomous parts: answering replies, auto approval, and the digest.

These are the pieces that act without a person watching, so the tests are mostly
about what the system refuses to do.
"""

import unittest

from jobseeker.models import Job, Reply
from jobseeker.outreach import digest
from jobseeker.outreach.responder import (
    auto_send_allowed,
    draft_reply,
    needs_a_person,
)
from jobseeker.persona import Persona

PROFILE = "data/profile.illona.json"


class TestReplySafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.persona = Persona.load(PROFILE)
        cls.job = Job(
            title="Frontend Engineer", company_name="Paystack", source="t", external_id="1"
        )

    def _reply(self, classification: str, snippet: str) -> Reply:
        return Reply(
            application_id=1,
            from_addr="ama.mensah@paystack.com",
            subject="Your application",
            snippet=snippet,
            classification=classification,
        )

    def test_a_commitment_question_needs_a_person(self):
        for snippet in (
            "What are your salary expectations?",
            "What is your notice period?",
            "Are you free on Tuesday at 10:00?",
            "Please book a slot on my calendly.",
        ):
            with self.subTest(snippet=snippet):
                blocked, reason = needs_a_person(self._reply("interested", snippet))
                self.assertTrue(blocked, reason)

    def test_an_offer_is_never_answered_automatically(self):
        blocked, _ = needs_a_person(self._reply("offer", "We are pleased to offer you the role."))
        self.assertTrue(blocked)

    def test_a_simple_question_does_not_need_a_person(self):
        blocked, _ = needs_a_person(self._reply("other", "Could you resend your portfolio link?"))
        self.assertFalse(blocked)

    def test_auto_send_is_refused_in_draft_mode(self):
        draft = draft_reply(self.persona, self._reply("rejection", "Unfortunately not this time."), self.job)
        allowed, why = auto_send_allowed(draft)
        self.assertFalse(allowed)
        self.assertIn("draft", why)

    def test_a_rejection_reply_is_gracious_and_short(self):
        draft = draft_reply(
            self.persona, self._reply("rejection", "Unfortunately we are not moving forward."), self.job
        )
        self.assertLess(len(draft.body.split()), 120)
        self.assertIn("Thank you", draft.body)
        for dash in "—–":
            self.assertNotIn(dash, draft.body)

    def test_an_interested_reply_names_the_role(self):
        draft = draft_reply(
            self.persona, self._reply("interested", "We would love to speak with you."), self.job
        )
        self.assertIn("Paystack", draft.body)

    def test_drafts_never_invent_a_meeting_time(self):
        draft = draft_reply(
            self.persona, self._reply("interested", "We would love to speak with you."), self.job
        )
        allowed, why = auto_send_allowed(draft)
        # Draft mode blocks it anyway, but the copy must not name a time either.
        self.assertNotRegex(draft.body.lower(), r"\b\d{1,2}[:.]\d{2}\b")
        del allowed, why


class TestWriterFallback(unittest.TestCase):
    """A failing model must never lose an application.

    The API can fail for reasons that have nothing to do with the code: an
    exhausted credit balance, a revoked key, a network blip. In every case the
    deterministic writer has to take over, because the alternative is a run that
    silently produces nothing.
    """

    def setUp(self):
        import os

        from jobseeker.llm import anthropic as anthropic_module

        self.module = anthropic_module
        self.previous = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-deliberately-invalid"
        anthropic_module._API_UNUSABLE[0] = False

    def tearDown(self):
        import os

        if self.previous is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = self.previous
        self.module._API_UNUSABLE[0] = False

    def test_an_unusable_key_falls_back_to_the_template(self):
        from jobseeker.llm import get_writer

        persona = Persona.load(PROFILE)
        job = Job(
            title="Frontend Engineer",
            company_name="Linear",
            source="ashby",
            external_id="1",
            description="Build product surfaces in React and TypeScript. " * 20,
        )
        draft = get_writer("claude").write(persona, job)
        self.assertIn("template", draft.generator)
        self.assertTrue(draft.email_body)
        self.assertIn("Linear", draft.email_body)

    def test_a_permanent_failure_is_remembered(self):
        self.assertFalse(
            self.module.mark_unusable_if_permanent(RuntimeError("temporary network blip"))
        )
        self.assertTrue(self.module.is_available())
        self.assertTrue(
            self.module.mark_unusable_if_permanent(
                RuntimeError("Your credit balance is too low to access the Anthropic API")
            )
        )
        self.assertFalse(self.module.is_available())


class TestDigest(unittest.TestCase):
    def test_the_digest_summarises_what_matters(self):
        stats = {
            "applications_by_status": {"draft": 3, "approved": 1},
            "jobs_by_status": {"shortlisted": 12},
            "sent_today": 4,
            "daily_cap": 12,
            "jobs_total": 900,
            "sent": 20,
            "reply_rate": 0.15,
            "positive": 2,
        }
        subject, body = digest.compose(
            stats, {"new_replies": 2, "needs_you": ["Web Developer at Canonical"]}, "Illona"
        )
        self.assertIn("4 sent", subject)
        self.assertIn("Illona", body)
        self.assertIn("Web Developer at Canonical", body)
        self.assertIn("NEEDS A DECISION", body)

    def test_the_columns_survive_the_style_guard(self):
        _, body = digest.compose({"sent_today": 0, "daily_cap": 12}, {}, "Illona")
        # The guard collapses runs of spaces, so alignment uses dot leaders.
        self.assertIn("....", body)

    def test_no_dashes_reach_the_digest(self):
        _, body = digest.compose(
            {"sent_today": 1, "daily_cap": 12}, {"needs_you": ["A role, at, a company"]}, "Illona"
        )
        for dash in "—–":
            self.assertNotIn(dash, body)


if __name__ == "__main__":
    unittest.main()


class TestBounceHandling(unittest.TestCase):
    """A bounce is not a reply, and must not be treated as a delivered application."""

    BOUNCE_BODY = (
        "Address not found. Your message wasn't delivered to careers@rancard.com "
        "because the domain rancard.com couldn't be found. The response was: 550 5.1.1"
    )

    def test_a_bounce_is_recognised(self):
        from jobseeker.outreach.inbox import classify_reply

        self.assertEqual(
            classify_reply(
                "Delivery Status Notification (Failure)",
                self.BOUNCE_BODY,
                use_llm=False,
                sender="mailer-daemon@googlemail.com",
            ),
            "bounce",
        )

    def test_the_failed_address_is_extracted(self):
        from jobseeker.outreach.inbox import bounced_address

        self.assertEqual(
            bounced_address(self.BOUNCE_BODY, "applicant@example.com"),
            "careers@rancard.com",
        )

    def test_a_bounce_marks_the_application_failed(self):
        from jobseeker.outreach.inbox import STATUS_FOR_CLASSIFICATION

        self.assertEqual(STATUS_FOR_CLASSIFICATION["bounce"], "failed")

    def test_a_real_rejection_is_not_mistaken_for_a_bounce(self):
        from jobseeker.outreach.inbox import classify_reply

        self.assertEqual(
            classify_reply(
                "Your application",
                "Unfortunately we have decided not to move forward at this time.",
                use_llm=False,
                sender="ama@company.com",
            ),
            "rejection",
        )


class TestDeliverability(unittest.TestCase):
    def test_a_domain_with_no_mail_server_is_blocked(self):
        from jobseeker.util.dns import address_deliverable

        ok, why = address_deliverable("someone@definitely-not-a-real-domain-xyz123.test")
        self.assertFalse(ok)
        self.assertTrue(why)

    def test_a_malformed_address_is_blocked(self):
        from jobseeker.util.dns import address_deliverable

        self.assertFalse(address_deliverable("not-an-address")[0])

    def test_a_real_domain_passes(self):
        from jobseeker.util.dns import address_deliverable

        self.assertTrue(address_deliverable("someone@gmail.com")[0])


class TestFormAnswers(unittest.TestCase):
    """The free text answers are the part of an application that must sound human."""

    @classmethod
    def setUpClass(cls):
        cls.persona = Persona.load(PROFILE)
        cls.job = Job(
            title="Product Engineer",
            company_name="Linear",
            source="ashby",
            external_id="1",
            description="Work with founders, product and design to build in React and TypeScript.",
        )

    def _answers(self):
        from jobseeker.llm.answers import build

        return build(self.persona, self.job, tailor=False)

    def test_every_stored_answer_is_returned(self):
        answers = self._answers()
        self.assertGreaterEqual(len(answers), 5)
        keys = {a["key"] for a in answers}
        self.assertIn("something_you_built", keys)
        self.assertIn("why_this_company", keys)

    def test_placeholders_are_filled_in(self):
        answer = next(a for a in self._answers() if a["key"] == "why_this_company")
        self.assertIn("Linear", answer["answer"])
        self.assertNotIn("{", answer["answer"])

    def test_technology_names_keep_their_capitals(self):
        answer = next(a for a in self._answers() if a["key"] == "why_this_company")
        # Quoting the posting verbatim, rather than lowercasing it, is what keeps
        # "React and TypeScript" from reading as carelessness.
        self.assertNotIn("react and typescript", answer["answer"])

    def test_answers_obey_the_house_style(self):
        for answer in self._answers():
            with self.subTest(key=answer["key"]):
                for dash in "—–":
                    self.assertNotIn(dash, answer["answer"])

    def test_salary_is_never_machine_written(self):
        from jobseeker.llm.answers import NEVER_GENERATE

        self.assertIn("salary", NEVER_GENERATE)


class TestAnswerCacheVersioning(unittest.TestCase):
    """An edit to the answer bank must reach applications already opened."""

    def test_every_answer_carries_the_bank_version(self):
        from jobseeker.llm.answers import bank_version, build

        persona = Persona.load(PROFILE)
        job = Job(title="Engineer", company_name="Acme", source="t", external_id="1",
                  description="React and TypeScript.")
        answers = build(persona, job, tailor=False)
        self.assertTrue(answers)
        for answer in answers:
            self.assertEqual(answer["version"], bank_version())

    def test_the_version_changes_when_the_bank_changes(self):
        import tempfile
        import pathlib

        from jobseeker.llm.answers import bank_version

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "answers.json"
            path.write_text('{"a": {"question": "q", "answer": "one"}}')
            first = bank_version(path)
            path.write_text('{"a": {"question": "q", "answer": "two"}}')
            self.assertNotEqual(first, bank_version(path))

    def test_the_interview_staples_are_all_present(self):
        from jobseeker.llm.answers import load

        keys = set(load())
        for expected in ("about_yourself", "teamwork", "strength_weakness", "outside_work"):
            self.assertIn(expected, keys)
