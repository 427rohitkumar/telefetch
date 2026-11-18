"""
Data models and structure definitions for TeleFetch.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class AuthState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CODE_REQUIRED = "CODE_REQUIRED"
    PASSWORD_REQUIRED = "PASSWORD_REQUIRED"
    AUTHORIZED = "AUTHORIZED"
    ERROR = "ERROR"


@dataclass
class ChannelInfo:
    id: int
    title: str
    username: Optional[str] = None
    is_channel: bool = True
    is_group: bool = False
    participants_count: Optional[int] = None
    entity_input: str = ""

    @property
    def display_name(self) -> str:
        if self.username:
            return f"{self.title} (@{self.username})"
        return f"{self.title} (ID: {self.id})"


@dataclass
class TelegramFileInfo:
    message_id: int
    file_name: str
    file_size: int  # in bytes
    date: datetime
    mime_type: str = ""
    extension: str = ""
    selected: bool = True
    channel_id: int = 0
    channel_title: str = ""

    @property
    def formatted_size(self) -> str:
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    @property
    def formatted_date(self) -> str:
        if self.date:
            return self.date.strftime("%Y-%m-%d %H:%M:%S")
        return "N/A"


@dataclass
class DownloadProgress:
    current_file_index: int = 0
    total_files: int = 0
    current_file_name: str = ""
    current_file_downloaded: int = 0
    current_file_total: int = 0
    total_bytes_downloaded: int = 0
    total_bytes_all: int = 0
    speed_bps: float = 0.0
    status_text: str = ""
    is_waiting_flood: bool = False
    flood_wait_seconds: int = 0
    is_cancelled: bool = False
    is_finished: bool = False
    zip_path: Optional[str] = None

    @property
    def current_file_percent(self) -> float:
        if self.current_file_total > 0:
            return min(1.0, max(0.0, self.current_file_downloaded / self.current_file_total))
        return 0.0

    @property
    def overall_percent(self) -> float:
        if self.total_files > 0:
            return min(1.0, max(0.0, self.current_file_index / self.total_files))
        return 0.0

    @property
    def formatted_speed(self) -> str:
        speed = self.speed_bps
        for unit in ["B/s", "KB/s", "MB/s", "GB/s"]:
            if speed < 1024.0:
                return f"{speed:.2f} {unit}"
            speed /= 1024.0
        return f"{speed:.2f} TB/s"


@dataclass
class PDFFileInfo:
    path: str
    file_name: str
    file_size: int
    page_count: int
    is_encrypted: bool = False

    @property
    def formatted_size(self) -> str:
        size = float(self.file_size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"


@dataclass
class MergeProgress:
    current_index: int = 0
    total_files: int = 0
    current_file_name: str = ""
    pages_added: int = 0
    total_pages_merged: int = 0
    status_text: str = ""
    is_finished: bool = False
    is_cancelled: bool = False
    output_path: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def overall_percent(self) -> float:
        if self.total_files > 0:
            return min(1.0, max(0.0, self.current_index / self.total_files))
        return 0.0
