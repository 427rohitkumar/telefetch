"""
Unit tests for configuration manager.
"""

import os
import shutil
import tempfile
import unittest
from src.config import AppConfig, ConfigManager


class TestConfigManager(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_mgr = ConfigManager(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_config(self):
        cfg = self.config_mgr.config
        self.assertEqual(cfg.api_id, "")
        self.assertEqual(cfg.default_extension, ".pdf")
        self.assertTrue(cfg.compress_to_zip)

    def test_save_and_reload(self):
        cfg = self.config_mgr.config
        cfg.api_id = "12345"
        cfg.api_hash = "abcdef123456"
        cfg.phone = "+919999999999"
        self.config_mgr.save(cfg)

        reloaded_mgr = ConfigManager(base_dir=self.test_dir)
        self.assertEqual(reloaded_mgr.config.api_id, "12345")
        self.assertEqual(reloaded_mgr.config.api_hash, "abcdef123456")
        self.assertEqual(reloaded_mgr.config.phone, "+919999999999")

    def test_do_not_remember_credentials(self):
        cfg = self.config_mgr.config
        cfg.api_id = "12345"
        cfg.api_hash = "abcdef123456"
        cfg.phone = "+919999999999"
        cfg.remember_credentials = False
        self.config_mgr.save(cfg)

        reloaded_mgr = ConfigManager(base_dir=self.test_dir)
        self.assertEqual(reloaded_mgr.config.api_id, "")
        self.assertEqual(reloaded_mgr.config.api_hash, "")
        self.assertEqual(reloaded_mgr.config.phone, "")


if __name__ == "__main__":
    unittest.main()
