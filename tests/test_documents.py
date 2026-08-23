"""The PDF writer has no library behind it, so it needs its own checks."""

import tempfile
import unittest
from pathlib import Path

from jobseeker.documents.pdf import Document, text_width, wrap


class TestPdf(unittest.TestCase):
    def test_measurement_matches_helvetica_metrics(self):
        # 'space' is 278/1000 em, so ten spaces at 10pt is 27.8pt.
        self.assertAlmostEqual(text_width(" " * 10, "regular", 10), 27.8, places=2)
        self.assertGreater(text_width("W", "bold", 12), text_width("i", "bold", 12))

    def test_wrapping_respects_the_measured_width(self):
        lines = wrap("word " * 60, "regular", 10, 200)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(text_width(line, "regular", 10), 200)

    def test_a_long_document_paginates(self):
        doc = Document()
        for _ in range(80):
            doc.paragraph("A paragraph of body copy that takes up vertical space. " * 3)
        self.assertGreater(len(doc.pages), 1)

    def test_output_is_a_valid_pdf_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Document()
            doc.title = "Test"
            doc.paragraph("Illona Addae", "name")
            doc.accent_bar()
            doc.bullets(["One point", "Another point"])
            path = doc.save(Path(tmp) / "out.pdf")
            raw = path.read_bytes()

        self.assertTrue(raw.startswith(b"%PDF-1.7"))
        self.assertIn(b"startxref", raw)
        self.assertTrue(raw.rstrip().endswith(b"%%EOF"))

    def test_pasted_dashes_never_reach_the_page(self):
        doc = Document()
        doc.paragraph("Frontend — Engineer")
        stream = " ".join(doc.pages[0].ops)
        self.assertNotIn("—", stream)


if __name__ == "__main__":
    unittest.main()
