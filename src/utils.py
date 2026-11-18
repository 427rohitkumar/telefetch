"""
Utility functions for TeleFetch: pattern matching, file sanitization, channel parser, formatters.
"""

import fnmatch
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def get_default_export_dir() -> str:
    """Returns the default download directory for Telegram exports."""
    home = Path.home()
    export_dir = home / "Downloads" / "Telegram_Exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    return str(export_dir)


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """
    Sanitizes a filename by removing or replacing illegal characters for Windows and Unix.
    """
    if not name:
        return "unnamed_file"

    # Replace invalid filesystem characters: < > : " / \ | ? * and control chars
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip()
    
    # Remove leading/trailing dots and spaces
    clean = clean.strip(". ")
    if not clean:
        clean = "unnamed_file"

    # Limit maximum length while preserving extension
    if len(clean) > max_length:
        base, ext = os.path.splitext(clean)
        keep_len = max_length - len(ext)
        if keep_len > 0:
            clean = base[:keep_len].rstrip(". ") + ext
        else:
            clean = clean[:max_length]

    return clean


def parse_channel_input(raw_input: str) -> Tuple[str, bool]:
    """
    Parses a raw user input into an entity identifier or invite link.
    Returns (cleaned_target, is_invite_hash).
    
    Handles:
    - @username -> 'username'
    - https://t.me/username -> 'username'
    - https://t.me/+AbCdEf... -> ('AbCdEf...', True)
    - https://t.me/joinchat/AbCdEf... -> ('AbCdEf...', True)
    - +AbCdEf... -> ('AbCdEf...', True)
    - -100123456789 -> integer ID or string
    - 123456789 -> integer ID or string
    """
    target = raw_input.strip()
    if not target:
        return "", False

    # Check for invite links
    invite_patterns = [
        r"(?:https?://)?(?:t\.me|telegram\.me)/\+([a-zA-Z0-9_\-]+)",
        r"(?:https?://)?(?:t\.me|telegram\.me)/joinchat/([a-zA-Z0-9_\-]+)",
        r"^\+([a-zA-Z0-9_\-]+)$",
    ]
    for pat in invite_patterns:
        match = re.search(pat, target)
        if match:
            return match.group(1), True

    # Check for direct URL: https://t.me/channel_name
    url_pattern = r"(?:https?://)?(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{4,})"
    match = re.search(url_pattern, target)
    if match:
        return match.group(1), False

    # Check for @username
    if target.startswith("@"):
        return target[1:].strip(), False

    # Check for numeric channel ID e.g. -100... or numeric
    if re.match(r"^-?\d+$", target):
        return target, False

    return target, False


def matches_pattern(filename: str, pattern: str) -> bool:
    """
    Checks if a filename matches a user pattern.
    If pattern is empty, matches everything.
    Tries regex matching first; falls back to case-insensitive wildcard fnmatch.
    """
    if not pattern or not pattern.strip():
        return True

    pattern = pattern.strip()
    
    # Try Regex first
    try:
        if re.search(pattern, filename, re.IGNORECASE):
            return True
    except re.error:
        pass

    # Fallback to wildcard matching (* and ?)
    try:
        lower_name = filename.lower()
        lower_pattern = pattern.lower()
        if not any(c in lower_pattern for c in ["*", "?", "["]):
            # Substring match if no wildcard symbols
            return lower_pattern in lower_name
        return fnmatch.fnmatch(lower_name, lower_pattern)
    except Exception:
        return False


def is_valid_regex(pattern: str) -> Tuple[bool, Optional[str]]:
    """Validates regex syntax, returning (is_valid, error_message)."""
    if not pattern:
        return True, None
    try:
        re.compile(pattern)
        return True, None
    except re.error as e:
        return False, str(e)


def format_bytes(size: int) -> str:
    """Formats byte count to human-readable string (KB, MB, GB)."""
    s = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if s < 1024.0:
            return f"{s:.2f} {unit}"
        s /= 1024.0
    return f"{s:.2f} PB"


def parse_date_str(date_str: str) -> Optional[datetime]:
    """Parses date string in formats like YYYY-MM-DD or YYYY/MM/DD."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None
