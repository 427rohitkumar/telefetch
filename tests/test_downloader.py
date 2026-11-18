"""
Unit tests for the ZIP compression and packaging pipeline.
"""

import os
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime

from src.models import DownloadProgress, TelegramFileInfo
from src.utils import sanitize_filename


class TestDownloadAndZip(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_zip_creation_and_contents(self):
        # Create simulated files
        test_files = [
            ("report_2026.pdf", b"%PDF-1.4 sample pdf content 1"),
            ("notes.pdf", b"%PDF-1.4 sample pdf content 2"),
            ("report_2026.pdf", b"%PDF-1.4 sample duplicate filename content"),
        ]

        zip_path = os.path.join(self.test_dir, "test_channel_export_20260930_120000.zip")
        temp_dir = tempfile.mkdtemp(dir=self.test_dir)

        used_filenames = set()
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, content in test_files:
                raw_name = sanitize_filename(name)
                clean_name = raw_name
                counter = 1
                base_n, ext_n = os.path.splitext(raw_name)
                while clean_name in used_filenames:
                    clean_name = f"{base_n}_{counter}{ext_n}"
                    counter += 1
                used_filenames.add(clean_name)

                # Write to temp file
                tmp_path = os.path.join(temp_dir, clean_name)
                with open(tmp_path, "wb") as f:
                    f.write(content)

                zf.write(tmp_path, arcname=clean_name)
                os.remove(tmp_path)

        self.assertTrue(os.path.exists(zip_path))

        # Inspect ZIP archive contents
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("report_2026.pdf", namelist)
            self.assertIn("notes.pdf", namelist)
            self.assertIn("report_2026_1.pdf", namelist)

            # Check content
            content1 = zf.read("report_2026.pdf")
            self.assertEqual(content1, b"%PDF-1.4 sample pdf content 1")
            content_dup = zf.read("report_2026_1.pdf")
            self.assertEqual(content_dup, b"%PDF-1.4 sample duplicate filename content")

    def test_download_progress_metrics(self):
        prog = DownloadProgress(
            current_file_index=5,
            total_files=10,
            current_file_downloaded=500,
            current_file_total=1000,
            speed_bps=2048,
        )
        self.assertEqual(prog.overall_percent, 0.5)
        self.assertEqual(prog.current_file_percent, 0.5)
        self.assertEqual(prog.formatted_speed, "2.00 KB/s")


if __name__ == "__main__":
    unittest.main()
