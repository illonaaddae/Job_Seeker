"""Which addresses an application may be sent to, and the suppression list.

Every case below is a real address the engine actually harvested, or the
direct consequence of one. Two of them were approved for sending before these
rules existed:

  help@kuda.com                          a customer support inbox
  antispamproofcareers@chippercash.com   an anti-scrape trap

The trap is the expensive one. Writing to it can get the sender's domain
listed as a spam source, and that cost lands on every later application
rather than on the one that tripped it.
"""

import tempfile
import unittest
from pathlib import Path

from jobseeker.db import Database
from jobseeker.enrich.finder import is_sendable


class TestSendableAddresses(unittest.TestCase):
    def test_keeps_real_hiring_inboxes(self):
        for email in (
            "careers@eversend.co",
            "jobs@example.com",
            "recruitment@example.com",
            "talent@example.com",
            "hr@example.com",
            "people@example.com",
            "info@turntabl.io",
            "hello@example.com",
            "contact@example.com",
            "ama.mensah@example.com",
        ):
            with self.subTest(email=email):
                self.assertTrue(is_sendable(email), f"{email} should be sendable")

    def test_blocks_anti_scrape_traps(self):
        """The exact address that got past the old filter, and its family."""
        for email in (
            "antispamproofcareers@chippercash.com",
            "anti-spam@example.com",
            "spamtrap@example.com",
            "spam-trap-careers@example.com",
            "spamproofjobs@example.com",
            "nospam@example.com",
            "honeypot@example.com",
            "donotharvest@example.com",
            "noharvest-careers@example.com",
            "donotcontact@example.com",
            "scrapers@example.com",
        ):
            with self.subTest(email=email):
                self.assertFalse(is_sendable(email), f"{email} is a trap and must be refused")

    def test_blocks_help_which_slipped_past_support_and_helpdesk(self):
        """`support` and `helpdesk` were blocked as substrings, `help` was not."""
        self.assertFalse(is_sendable("help@kuda.com"))
        self.assertFalse(is_sendable("support@example.com"))
        self.assertFalse(is_sendable("helpdesk@example.com"))

    def test_blocks_inboxes_that_are_not_hiring(self):
        for email in (
            "press@example.com",
            "media@example.com",
            "marketing@example.com",
            "newsletter@example.com",
            "complaints@example.com",
            "refunds@example.com",
            "customercare@example.com",
            "billing@example.com",
            "no-reply@example.com",
            "postmaster@example.com",
            "abuse@example.com",
        ):
            with self.subTest(email=email):
                self.assertFalse(is_sendable(email))

    def test_exact_blocks_do_not_catch_real_words_containing_them(self):
        """`help` is blocked only as the whole local part, not as a substring,
        so a person whose name contains it is still reachable."""
        self.assertTrue(is_sendable("helper.ama@example.com"))
        self.assertTrue(is_sendable("mediana@example.com"))

    def test_rejects_malformed(self):
        for email in ("", "not-an-address", "@example.com", "two@@example.com"):
            with self.subTest(email=email):
                self.assertFalse(is_sendable(email))


class TestSuppressions(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        # Database builds its own schema on construction.
        self.db = Database(str(Path(self.dir.name) / "test.db"))

    def tearDown(self):
        self.dir.cleanup()

    def test_suppresses_a_single_address(self):
        self.assertFalse(self.db.is_suppressed("help@kuda.com"))
        self.db.add_suppression("help@kuda.com", "support inbox")
        self.assertTrue(self.db.is_suppressed("help@kuda.com"))
        self.assertFalse(self.db.is_suppressed("careers@kuda.com"))

    def test_suppresses_a_whole_domain(self):
        self.db.add_suppression("@chippercash.com", "publishes a scrape trap")
        self.assertTrue(self.db.is_suppressed("antispamproofcareers@chippercash.com"))
        self.assertTrue(self.db.is_suppressed("anything@chippercash.com"))
        self.assertFalse(self.db.is_suppressed("careers@eversend.co"))

    def test_is_case_and_space_insensitive(self):
        self.db.add_suppression("  HELP@Kuda.COM  ")
        self.assertTrue(self.db.is_suppressed("help@kuda.com"))
        self.assertTrue(self.db.is_suppressed("  Help@Kuda.com "))

    def test_an_empty_address_is_never_sendable(self):
        self.assertTrue(self.db.is_suppressed(""))

    def test_removing_one(self):
        self.db.add_suppression("help@kuda.com")
        self.assertTrue(self.db.remove_suppression("help@kuda.com"))
        self.assertFalse(self.db.is_suppressed("help@kuda.com"))
        # Removing something that was never there is not an error.
        self.assertFalse(self.db.remove_suppression("help@kuda.com"))

    def test_listing_carries_the_reason(self):
        self.db.add_suppression("help@kuda.com", "support inbox")
        rows = self.db.suppression_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pattern"], "help@kuda.com")
        self.assertEqual(rows[0]["reason"], "support inbox")

    def test_adding_twice_keeps_one(self):
        self.db.add_suppression("help@kuda.com", "first")
        self.db.add_suppression("help@kuda.com", "second")
        self.assertEqual(len(self.db.suppression_rows()), 1)


if __name__ == "__main__":
    unittest.main()
