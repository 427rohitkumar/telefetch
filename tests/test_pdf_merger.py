"""
Unit tests for PDF Slicing and Master PDF Merging functionality.
"""

import os
import shutil
import tempfile
import unittest

import pypdf
from src.pdf_merger import PDFMerger, inspect_pdf_file


def create_dummy_pdf(file_path: str, num_pages: int):
    """Helper to generate a valid dummy PDF with a specified number of blank pages."""
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=595.276, height=841.89)  # Standard A4
    with open(file_path, "wb") as f:
        writer.write(f)


class TestPDFMerger(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.merger = PDFMerger()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_inspect_pdf(self):
        pdf_path = os.path.join(self.test_dir, "sample_10.pdf")
        create_dummy_pdf(pdf_path, num_pages=10)

        info = inspect_pdf_file(pdf_path)
        self.assertIsNotNone(info)
        self.assertEqual(info.file_name, "sample_10.pdf")
        self.assertEqual(info.page_count, 10)
        self.assertFalse(info.is_encrypted)
        self.assertGreater(info.file_size, 0)

    def test_slicing_and_merging_with_page_limit(self):
        # Create 3 PDFs:
        # doc_1.pdf has 5 pages (< 30, all 5 should be extracted)
        # doc_2.pdf has 35 pages (> 30, only 30 should be extracted)
        # doc_10.pdf has 10 pages (< 30, all 10 should be extracted)
        p1 = os.path.join(self.test_dir, "doc_1.pdf")
        p2 = os.path.join(self.test_dir, "doc_2.pdf")
        p10 = os.path.join(self.test_dir, "doc_10.pdf")

        create_dummy_pdf(p1, 5)
        create_dummy_pdf(p2, 35)
        create_dummy_pdf(p10, 10)

        info1 = inspect_pdf_file(p1)
        info2 = inspect_pdf_file(p2)
        info10 = inspect_pdf_file(p10)

        # Pass in disordered order to verify natural sorting
        files = [info10, info1, info2]

        out_pdf = os.path.join(self.test_dir, "Master_Merged.pdf")
        success, msg, final_path = self.merger.process_and_merge(
            files=files,
            output_path=out_pdf,
            pages_to_extract=30,
        )

        self.assertTrue(success)
        self.assertIsNotNone(final_path)
        self.assertTrue(os.path.exists(out_pdf))

        # Check merged PDF pages: 5 + 30 + 10 = 45 pages
        reader = pypdf.PdfReader(out_pdf)
        self.assertEqual(len(reader.pages), 45)

    def test_cancellation(self):
        p1 = os.path.join(self.test_dir, "test.pdf")
        create_dummy_pdf(p1, 10)
        info = inspect_pdf_file(p1)

        self.merger.cancel()
        out_pdf = os.path.join(self.test_dir, "Cancelled_Merged.pdf")
        success, msg, final_path = self.merger.process_and_merge(
            files=[info],
            output_path=out_pdf,
            pages_to_extract=5,
        )

        self.assertFalse(success)
        self.assertIn("cancelled", msg.lower())


if __name__ == "__main__":
    unittest.main()
