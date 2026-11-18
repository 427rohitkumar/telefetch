"""
Download pipeline for TeleFetch: handles chunked downloading, rate-limit recovery (FloodWait),
ZIP archiving, and real-time speed & progress calculation.
"""

import asyncio
import os
import shutil
import tempfile
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from telethon import errors

from src.models import DownloadProgress, TelegramFileInfo
from src.telegram_client import TelegramBackend
from src.utils import sanitize_filename


class Downloader:
    """
    Orchestrates the downloading of selected Telegram files into a folder or ZIP archive.
    """

    def __init__(self, backend: TelegramBackend):
        self.backend = backend
        self.cancel_event = threading.Event()

    def cancel(self):
        """Signals the download process to halt gracefully."""
        self.cancel_event.set()

    def start_download(
        self,
        files: List[TelegramFileInfo],
        output_dir: str,
        compress_to_zip: bool,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        on_complete_callback: Optional[Callable[[bool, str, Optional[str]], None]] = None,
    ):
        """
        Launches download pipeline on the backend asyncio event loop.
        """
        self.cancel_event.clear()
        fut = self.backend.run_coro(
            self._download_pipeline_async(
                files=files,
                output_dir=output_dir,
                compress_to_zip=compress_to_zip,
                progress_callback=progress_callback,
                log_callback=log_callback,
                on_complete_callback=on_complete_callback,
            )
        )
        return fut

    async def _download_pipeline_async(
        self,
        files: List[TelegramFileInfo],
        output_dir: str,
        compress_to_zip: bool,
        progress_callback: Optional[Callable[[DownloadProgress], None]],
        log_callback: Optional[Callable[[str], None]],
        on_complete_callback: Optional[Callable[[bool, str, Optional[str]], None]],
    ):
        def log(msg: str):
            if log_callback:
                log_callback(msg)

        if not files:
            log("No files selected for download.")
            if on_complete_callback:
                on_complete_callback(False, "No files selected", None)
            return

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        channel_title = sanitize_filename(files[0].channel_title or "TelegramChannel")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        zip_archive_path: Optional[Path] = None
        zip_file: Optional[zipfile.ZipFile] = None
        temp_dir: Optional[str] = None

        if compress_to_zip:
            zip_filename = f"{channel_title}_export_{timestamp}.zip"
            zip_archive_path = out_path / zip_filename
            temp_dir = tempfile.mkdtemp(prefix="telefetch_")
            log(f"Creating ZIP archive: {zip_archive_path}")
            zip_file = zipfile.ZipFile(zip_archive_path, mode="w", compression=zipfile.ZIP_DEFLATED)
        else:
            log(f"Downloading files to directory: {out_path}")

        total_files = len(files)
        total_bytes = sum(f.file_size for f in files)
        downloaded_bytes_total = 0
        used_filenames = set()

        progress = DownloadProgress(
            current_file_index=0,
            total_files=total_files,
            total_bytes_all=total_bytes,
            status_text="Starting download...",
        )

        success_count = 0
        failed_count = 0

        try:
            for idx, file_info in enumerate(files):
                if self.cancel_event.is_set():
                    log("Download cancelled by user.")
                    progress.is_cancelled = True
                    progress.status_text = "Download cancelled."
                    if progress_callback:
                        progress_callback(progress)
                    break

                # Resolve unique filename
                raw_name = sanitize_filename(file_info.file_name)
                clean_name = raw_name
                counter = 1
                base_n, ext_n = os.path.splitext(raw_name)
                while clean_name in used_filenames:
                    clean_name = f"{base_n}_{counter}{ext_n}"
                    counter += 1
                used_filenames.add(clean_name)

                progress.current_file_index = idx + 1
                progress.current_file_name = clean_name
                progress.current_file_downloaded = 0
                progress.current_file_total = file_info.file_size
                progress.status_text = f"Downloading [{idx+1}/{total_files}]: {clean_name}"

                log(f"[{idx+1}/{total_files}] Downloading: {clean_name} ({file_info.formatted_size})")

                # Destination for this file
                if compress_to_zip:
                    target_file_path = os.path.join(temp_dir, clean_name)
                else:
                    target_file_path = str(out_path / clean_name)

                # Download with retry and FloodWait handling
                success = await self._download_single_file_with_retry(
                    file_info=file_info,
                    target_file_path=target_file_path,
                    progress=progress,
                    progress_callback=progress_callback,
                    log=log,
                )

                if success:
                    success_count += 1
                    downloaded_bytes_total += file_info.file_size
                    progress.total_bytes_downloaded = downloaded_bytes_total

                    if compress_to_zip and zip_file:
                        log(f"Archiving into ZIP: {clean_name}")
                        zip_file.write(target_file_path, arcname=clean_name)
                        try:
                            os.remove(target_file_path)
                        except OSError:
                            pass
                else:
                    failed_count += 1
                    log(f"Failed to download: {clean_name}")

                if progress_callback:
                    progress_callback(progress)

            progress.is_finished = True
            if compress_to_zip:
                progress.zip_path = str(zip_archive_path)

        finally:
            if zip_file:
                zip_file.close()
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

        if self.cancel_event.is_set():
            result_msg = f"Cancelled. Downloaded {success_count}/{total_files} files."
            if on_complete_callback:
                on_complete_callback(False, result_msg, str(zip_archive_path) if compress_to_zip else str(out_path))
        else:
            result_msg = f"Completed: {success_count} files downloaded successfully."
            if failed_count > 0:
                result_msg += f" ({failed_count} files failed)"
            log(result_msg)
            if on_complete_callback:
                on_complete_callback(True, result_msg, str(zip_archive_path) if compress_to_zip else str(out_path))

    async def _download_single_file_with_retry(
        self,
        file_info: TelegramFileInfo,
        target_file_path: str,
        progress: DownloadProgress,
        progress_callback: Optional[Callable[[DownloadProgress], None]],
        log: Callable[[str], None],
        max_retries: int = 3,
    ) -> bool:
        """Downloads a single file handling FloodWait and network interruptions."""
        last_time = time.time()
        last_bytes = 0

        def telethon_progress(received_bytes: int, total_bytes: int):
            nonlocal last_time, last_bytes
            now = time.time()
            elapsed = now - last_time
            if elapsed >= 0.5 or received_bytes == total_bytes:
                chunk = received_bytes - last_bytes
                speed = (chunk / elapsed) if elapsed > 0 else 0
                last_time = now
                last_bytes = received_bytes
                
                progress.current_file_downloaded = received_bytes
                progress.current_file_total = total_bytes
                progress.speed_bps = speed
                if progress_callback:
                    progress_callback(progress)

        for attempt in range(max_retries):
            if self.cancel_event.is_set():
                return False

            try:
                # Fetch message
                msg = await self.backend.client.get_messages(
                    file_info.channel_id,
                    ids=file_info.message_id
                )

                if not msg or not msg.media:
                    log(f"Message #{file_info.message_id} does not contain media or was deleted.")
                    return False

                # Download media
                await self.backend.client.download_media(
                    msg,
                    file=target_file_path,
                    progress_callback=telethon_progress,
                )
                return True

            except errors.FloodWaitError as fwe:
                wait_sec = fwe.seconds
                log(f"⚠️ Telegram Rate Limit! Pausing for {wait_sec} seconds before resuming...")
                progress.is_waiting_flood = True
                progress.flood_wait_seconds = wait_sec

                # Countdown sleep while respecting cancellation
                for remaining in range(wait_sec, 0, -1):
                    if self.cancel_event.is_set():
                        return False
                    progress.flood_wait_seconds = remaining
                    progress.status_text = f"Rate limited. Resuming in {remaining}s..."
                    if progress_callback:
                        progress_callback(progress)
                    await asyncio.sleep(1)

                progress.is_waiting_flood = False
                progress.status_text = "Resuming download..."
                if progress_callback:
                    progress_callback(progress)

            except Exception as e:
                log(f"Download attempt {attempt+1}/{max_retries} failed for '{file_info.file_name}': {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    return False

        return False
