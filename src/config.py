"""
Configuration management for TeleFetch: loads, saves, and validates application settings.
"""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils import get_default_export_dir

CONFIG_FILE_NAME = "telefetch_config.json"
SESSION_NAME = "telefetch_session"


@dataclass
class AppConfig:
    api_id: str = ""
    api_hash: str = ""
    phone: str = ""
    download_dir: str = ""
    compress_to_zip: bool = True
    default_extension: str = ".pdf"
    batch_scan_limit: int = 1000
    remember_credentials: bool = True
    appearance_mode: str = "Dark"
    last_channel: str = ""

    def __post_init__(self):
        if not self.download_dir:
            self.download_dir = get_default_export_dir()


class ConfigManager:
    """Manages reading and writing application settings."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.config_dir = Path(base_dir)
        else:
            # Default to local directory where app is running
            self.config_dir = Path(os.getcwd())
        
        self.config_file = self.config_dir / CONFIG_FILE_NAME
        self.session_path = self.config_dir / SESSION_NAME
        self._config = self.load()

    @property
    def config(self) -> AppConfig:
        return self._config

    def load(self) -> AppConfig:
        """Loads configuration from JSON file or returns defaults."""
        if not self.config_file.exists():
            cfg = AppConfig()
            self.save(cfg)
            return cfg

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Map json fields into AppConfig
            valid_keys = AppConfig.__annotations__.keys()
            filtered_data = {k: v for k, v in data.items() if k in valid_keys}
            return AppConfig(**filtered_data)
        except Exception:
            return AppConfig()

    def save(self, config: Optional[AppConfig] = None) -> bool:
        """Saves current or provided configuration to JSON file."""
        if config is not None:
            self._config = config
        
        try:
            # If remember_credentials is False, do not write sensitive fields
            data = asdict(self._config)
            if not self._config.remember_credentials:
                data["api_id"] = ""
                data["api_hash"] = ""
                data["phone"] = ""
                
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def clear_credentials(self):
        """Clears saved credentials and deletes session file."""
        self._config.api_id = ""
        self._config.api_hash = ""
        self._config.phone = ""
        self.save()

        # Delete session files if they exist
        for ext in [".session", ".session-journal"]:
            session_file = Path(f"{self.session_path}{ext}")
            if session_file.exists():
                try:
                    session_file.unlink()
                except OSError:
                    pass
