"""Scoring decides what gets applied to, so its blockers matter most."""

import unittest

from jobseeker.persona import Persona
from jobseeker.scoring import score_job

PROFILE = "data/profile.illona.json"

FRONTEND_JD = """
You will build and maintain customer facing interfaces in React and TypeScript.
You will work with designers in Figma and own deployment through our CI/CD pipeline.
We write tests with Vitest and care about accessibility and web performance.
We are looking for someone with 1+ years of experience. This role is fully remote.
""" * 3


class TestScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.persona = Persona.load(PROFILE)

    def test_a_strong_match_scores_high(self):
        result = score_job(
            self.persona,
            title="Junior Frontend Engineer",
            description=FRONTEND_JD,
            location="Remote",
            remote=1,
            posted_at="2026-08-20T00:00:00Z",
        )
        self.assertGreater(result.score, 75)
        self.assertFalse(result.blocked)
        self.assertIn("React", result.matched_skills)

    def test_senior_titles_are_blocked(self):
        result = score_job(self.persona, title="Senior Frontend Engineer", description=FRONTEND_JD)
        self.assertTrue(result.blocked)
        self.assertEqual(result.score, 0)

    def test_foreign_stacks_are_blocked(self):
        result = score_job(
            self.persona,
            title="Software Engineer, C++",
            description="Write C++ for our rendering pipeline. " * 30,
        )
        self.assertTrue(result.blocked)

    def test_excluded_keywords_block_the_job(self):
        result = score_job(
            self.persona,
            title="Frontend Engineer",
            description=FRONTEND_JD + " Requires a security clearance.",
        )
        self.assertTrue(any("security clearance" in b for b in result.blockers))

    def test_many_years_required_lowers_the_score(self):
        strong = score_job(
            self.persona, title="Frontend Engineer", description=FRONTEND_JD, remote=1
        )
        demanding = score_job(
            self.persona,
            title="Frontend Engineer",
            description=FRONTEND_JD + " You will need 7 years of experience.",
            remote=1,
        )
        self.assertLess(demanding.score, strong.score)

    def test_the_breakdown_explains_itself(self):
        result = score_job(self.persona, title="Frontend Engineer", description=FRONTEND_JD)
        self.assertEqual(
            set(result.signals),
            {"title", "skills", "seniority", "location", "freshness", "signal"},
        )
        self.assertTrue(all(isinstance(reason, str) for reason in result.reasons))


if __name__ == "__main__":
    unittest.main()
