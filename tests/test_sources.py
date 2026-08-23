"""Source adapters parse other people's JSON, which changes without warning."""

import unittest

from jobseeker.sources.ashby import _to_job as ashby_job
from jobseeker.sources.base import dedupe
from jobseeker.sources.greenhouse import _to_job as greenhouse_job
from jobseeker.sources.lever import _to_job as lever_job
from jobseeker.models import Job
from jobseeker.util.text import strip_html


class TestParsing(unittest.TestCase):
    def test_greenhouse_entity_encoded_html_is_stripped(self):
        job = greenhouse_job(
            "acme",
            {
                "id": 42,
                "title": "Frontend Engineer",
                "location": {"name": "Remote, EMEA"},
                "content": "&lt;p&gt;Build &lt;b&gt;interfaces&lt;/b&gt;&lt;/p&gt;",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/42",
                "first_published": "2026-08-01T00:00:00Z",
            },
        )
        self.assertEqual(job.description, "Build interfaces")
        self.assertEqual(job.remote, 1)
        self.assertEqual(job.external_id, "42")

    def test_lever_marks_remote_from_the_workplace_type(self):
        job = lever_job(
            "acme",
            {
                "id": "abc",
                "text": "Product Engineer",
                "categories": {"location": "Lagos", "commitment": "Full-time"},
                "workplaceType": "remote",
                "descriptionPlain": "Ship features.",
                "createdAt": 1750000000000,
            },
        )
        self.assertEqual(job.remote, 1)
        self.assertEqual(job.employment_type, "Full-time")
        self.assertTrue(job.posted_at.startswith("20"))

    def test_ashby_reads_the_remote_flag(self):
        job = ashby_job(
            "acme",
            {"id": "1", "title": "Engineer", "location": "Anywhere", "isRemote": True},
            "Acme Inc",
        )
        self.assertEqual(job.company_name, "Acme Inc")
        self.assertEqual(job.remote, 1)

    def test_html_stripping_keeps_list_structure(self):
        text = strip_html("<ul><li>One</li><li>Two</li></ul>")
        self.assertIn("- One", text)
        self.assertIn("- Two", text)


class TestDedupe(unittest.TestCase):
    def test_the_same_role_on_two_boards_collapses(self):
        jobs = [
            Job(title="Frontend Engineer", company_name="Acme", source="lever", external_id="1"),
            Job(title="frontend engineer", company_name="acme", source="greenhouse", external_id="2"),
            Job(title="Backend Engineer", company_name="Acme", source="lever", external_id="3"),
        ]
        self.assertEqual(len(dedupe(jobs)), 2)


if __name__ == "__main__":
    unittest.main()
