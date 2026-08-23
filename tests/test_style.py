"""The house style rules are the ones most likely to be broken silently."""

import unittest

from jobseeker.util.style import DASHES, audit, enforce, sanitise


class TestDashRemoval(unittest.TestCase):
    def test_spaced_em_dash_becomes_a_comma(self):
        self.assertEqual(sanitise("I build things — carefully."), "I build things, carefully.")

    def test_word_joining_dash_becomes_a_hyphen(self):
        self.assertEqual(sanitise("full—stack"), "full-stack")

    def test_every_dash_character_is_removed(self):
        for dash in DASHES:
            with self.subTest(dash=dash):
                self.assertNotIn(dash, sanitise(f"React {dash} TypeScript"))

    def test_salutation_commas_survive(self):
        cleaned = sanitise("Dear Ada,\n\nI am applying for the role.\n\nBest,\nIllona")
        self.assertIn("Dear Ada,", cleaned)
        self.assertIn("Best,", cleaned)

    def test_ordinary_hyphens_are_left_alone(self):
        self.assertEqual(sanitise("mobile-first design"), "mobile-first design")


class TestFillerRemoval(unittest.TestCase):
    def test_known_filler_is_rewritten(self):
        cleaned = sanitise("I hope this email finds you well. I want to leverage React.")
        self.assertNotIn("hope this email finds you well", cleaned.lower())
        self.assertIn("use React", cleaned)

    def test_stock_opener_is_replaced(self):
        cleaned = sanitise("I am writing to express my strong interest in the role.")
        self.assertTrue(cleaned.startswith("I am applying for"))


class TestAudit(unittest.TestCase):
    def test_generic_draft_is_flagged(self):
        report = audit("I would be a great fit for your company.", company="Acme", job_title="Engineer")
        self.assertFalse(report.clean)
        self.assertTrue(report.missing_specifics)

    def test_specific_draft_passes(self):
        text = (
            "I am applying for the Frontend Engineer role at Acme. I shipped a React 19 "
            "dashboard at oceaniccoder.dev that cut load time by 40%."
        )
        report = audit(text, company="Acme", job_title="Frontend Engineer")
        self.assertTrue(report.clean, report.summary())

    def test_word_limit_is_enforced(self):
        _, report = enforce("word " * 300, company="Acme", job_title="Engineer", max_words=220)
        self.assertIn("too long", report.summary())


if __name__ == "__main__":
    unittest.main()
