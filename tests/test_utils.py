"""
Unit tests for TeleFetch utilities.
"""

import unittest
from datetime import datetime
from src.utils import (
    format_bytes,
    is_valid_regex,
    matches_pattern,
    parse_channel_input,
    parse_date_str,
    sanitize_filename,
)


class TestUtils(unittest.TestCase):

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_name.pdf"), "valid_name.pdf")
        self.assertEqual(sanitize_filename('invalid:name/with*bad?chars".pdf'), "invalid_name_with_bad_chars_.pdf")
        self.assertEqual(sanitize_filename("...dotted..."), "dotted")
        self.assertEqual(sanitize_filename(""), "unnamed_file")

    def test_parse_channel_input(self):
        # Username with @
        target, is_invite = parse_channel_input("@tech_books")
        self.assertEqual(target, "tech_books")
        self.assertFalse(is_invite)

        # Telegram URL username
        target, is_invite = parse_channel_input("https://t.me/tech_books")
        self.assertEqual(target, "tech_books")
        self.assertFalse(is_invite)

        # Invite links
        target, is_invite = parse_channel_input("https://t.me/+AbCdEfGh123")
        self.assertEqual(target, "AbCdEfGh123")
        self.assertTrue(is_invite)

        target, is_invite = parse_channel_input("https://t.me/joinchat/AbCdEfGh123")
        self.assertEqual(target, "AbCdEfGh123")
        self.assertTrue(is_invite)

        target, is_invite = parse_channel_input("+AbCdEfGh123")
        self.assertEqual(target, "AbCdEfGh123")
        self.assertTrue(is_invite)

        # Channel ID
        target, is_invite = parse_channel_input("-1001234567890")
        self.assertEqual(target, "-1001234567890")
        self.assertFalse(is_invite)

    def test_matches_pattern(self):
        # Empty pattern matches everything
        self.assertTrue(matches_pattern("document.pdf", ""))

        # Wildcards
        self.assertTrue(matches_pattern("Report_2026_Q1.pdf", "Report_*.pdf"))
        self.assertTrue(matches_pattern("Report_2026_Q1.pdf", "*2026*"))
        self.assertFalse(matches_pattern("Invoice_123.pdf", "Report_*"))

        # Case-insensitivity
        self.assertTrue(matches_pattern("DOCUMENT.PDF", "document.pdf"))
        self.assertTrue(matches_pattern("Python_Book.pdf", "python_*"))

        # Regex
        self.assertTrue(matches_pattern("Doc_20260930.pdf", r"Doc_\d{8}\.pdf"))
        self.assertFalse(matches_pattern("Doc_abc.pdf", r"Doc_\d{8}\.pdf"))

    def test_is_valid_regex(self):
        valid, err = is_valid_regex(r"^test.*\.pdf$")
        self.assertTrue(valid)
        self.assertIsNone(err)

        valid, err = is_valid_regex(r"[unclosed_bracket")
        self.assertFalse(valid)
        self.assertIsNotNone(err)

    def test_format_bytes(self):
        self.assertEqual(format_bytes(500), "500.00 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1024 * 1024 * 5), "5.00 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024 * 2), "2.00 GB")

    def test_parse_date_str(self):
        dt = parse_date_str("2026-09-30")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 9)
        self.assertEqual(dt.day, 30)

        dt2 = parse_date_str("30-09-2026")
        self.assertIsNotNone(dt2)
        self.assertEqual(dt2.day, 30)

        self.assertIsNone(parse_date_str("invalid-date"))
        self.assertIsNone(parse_date_str(""))


if __name__ == "__main__":
    unittest.main()
