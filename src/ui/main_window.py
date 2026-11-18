"""
Main Window for TeleFetch GUI: Multi-Tab architecture supporting:
- Tab 1: "Telegram Downloader" (Bulk fetch & export to ZIP/directory)
- Tab 2: "PDF Split & Merger" (Slice first N pages and merge up to 100 PDFs)
"""

import os
import subprocess
import threading
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Optional
import customtkinter as ctk

from src.config import ConfigManager
from src.downloader import Downloader
from src.models import AuthState, ChannelInfo, DownloadProgress
from src.telegram_client import TelegramBackend
from src.ui.auth_modal import AuthModal
from src.ui.pdf_merger_tab import PDFMergerTab
from src.ui.table_view import FilePreviewTable
from src.ui.widgets import DualProgressBar, LogViewer, StatusBadge
from src.utils import (
    format_bytes,
    get_default_export_dir,
    is_valid_regex,
    parse_date_str,
    sanitize_filename,
)


class TeleFetchApp(ctk.CTk):
    """
    Main Application Window with Multi-Tab support.
    """

    def __init__(self):
        super().__init__()

        self.title("TeleFetch - Telegram Bulk Downloader & PDF Master Merger")
        self.geometry("1180x880")
        self.minsize(1020, 740)

        # Set appearance
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Core Services
        self.config_manager = ConfigManager()
        self.backend = TelegramBackend(self.config_manager)
        self.downloader = Downloader(self.backend)

        # State flags
        self.verified_channel: Optional[ChannelInfo] = None
        self.is_scanning = False
        self.is_downloading = False
        self.scan_cancel_event = threading.Event()

        self._build_ui()
        self._check_initial_auth()

    # -------------------------------------------------------------
    # UI Building
    # -------------------------------------------------------------

    def _build_ui(self):
        # Main layout container
        self.main_container = ctk.CTkFrame(self, fg_color="#0b1120", corner_radius=0)
        self.main_container.pack(fill="both", expand=True)

        self._build_header()

        # Multi-Tab View
        self.tabview = ctk.CTkTabview(
            self.main_container,
            fg_color="#0b1120",
            segmented_button_fg_color="#182234",
            segmented_button_selected_color="#0284c7",
            segmented_button_selected_hover_color="#0369a1",
            segmented_button_unselected_color="#1e293b",
            segmented_button_unselected_hover_color="#334155",
            text_color="#f8fafc",
        )
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        # Tab 1: Telegram Downloader
        self.tab_downloader = self.tabview.add("Telegram Downloader")
        self._build_downloader_tab(self.tab_downloader)

        # Tab 2: PDF Split & Merger
        self.tab_pdf_merger = self.tabview.add("PDF Split & Merger")
        self._build_pdf_merger_tab(self.tab_pdf_merger)

        # Bottom shared Log Console
        self._build_log_section()

    def _build_header(self):
        header = ctk.CTkFrame(self.main_container, fg_color="#0f172a", height=58, corner_radius=0)
        header.pack(fill="x", padx=0, pady=(0, 4))

        # Brand / Title
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.pack(side="left", padx=16, pady=8)

        logo_title = ctk.CTkLabel(
            brand_frame,
            text="⚡ TeleFetch",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#38bdf8",
        )
        logo_title.pack(side="left")

        sub_title = ctk.CTkLabel(
            brand_frame,
            text="Telegram Bulk Downloader & PDF Master Suite",
            font=ctk.CTkFont(size=12),
            text_color="#64748b",
        )
        sub_title.pack(side="left", padx=(10, 0), pady=(4, 0))

        # Auth Controls (Right)
        auth_frame = ctk.CTkFrame(header, fg_color="transparent")
        auth_frame.pack(side="right", padx=16, pady=8)

        self.status_badge = StatusBadge(auth_frame)
        self.status_badge.pack(side="left", padx=(0, 12))

        self.login_btn = ctk.CTkButton(
            auth_frame,
            text="🔑 Login / API Settings",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=32,
            command=self._open_auth_modal,
        )
        self.login_btn.pack(side="left", padx=(0, 6))

        self.logout_btn = ctk.CTkButton(
            auth_frame,
            text="Logout",
            font=ctk.CTkFont(size=12),
            fg_color="#334155",
            hover_color="#475569",
            width=70,
            height=32,
            command=self._on_logout,
        )
        self.logout_btn.pack(side="left")

    def _build_downloader_tab(self, parent):
        """Builds all controls for Tab 1: Telegram Downloader."""
        self._build_target_section(parent)
        self._build_filter_section(parent)
        self._build_table_section(parent)
        self._build_export_section(parent)

    def _build_pdf_merger_tab(self, parent):
        """Builds all controls for Tab 2: PDF Split & Merger."""
        self.pdf_merger_view = PDFMergerTab(parent, log_callback=self.log)
        self.pdf_merger_view.pack(fill="both", expand=True)

    def _build_target_section(self, parent):
        # Target Card
        target_card = ctk.CTkFrame(parent, fg_color="#182234", corner_radius=10)
        target_card.pack(fill="x", padx=8, pady=(8, 8))

        row1 = ctk.CTkFrame(target_card, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(
            row1,
            text="Target Channel / Chat:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e2e8f0",
            width=150,
            anchor="w",
        ).pack(side="left")

        self.channel_entry = ctk.CTkEntry(
            row1,
            placeholder_text="Enter @username, invite link (https://t.me/+...), or Channel ID (-100...)",
            height=36,
        )
        self.channel_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if self.config_manager.config.last_channel:
            self.channel_entry.insert(0, self.config_manager.config.last_channel)

        self.verify_btn = ctk.CTkButton(
            row1,
            text="🔍 Verify Channel",
            width=120,
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self._on_verify_channel,
        )
        self.verify_btn.pack(side="left", padx=(0, 6))

        self.fetch_btn = ctk.CTkButton(
            row1,
            text="🚀 Fetch Files",
            width=110,
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            command=self._on_start_fetch,
        )
        self.fetch_btn.pack(side="left", padx=(0, 6))

        self.stop_fetch_btn = ctk.CTkButton(
            row1,
            text="⏹ Stop",
            width=70,
            height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#ef4444",
            hover_color="#dc2626",
            state="disabled",
            command=self._on_stop_fetch,
        )
        self.stop_fetch_btn.pack(side="left")

        # Row 2: Channel verification info indicator
        self.channel_info_lbl = ctk.CTkLabel(
            target_card,
            text="Please verify your target channel or click 'Fetch Files' to begin.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
            anchor="w",
        )
        self.channel_info_lbl.pack(fill="x", padx=14, pady=(0, 8))

    def _build_filter_section(self, parent):
        filter_card = ctk.CTkFrame(parent, fg_color="#182234", corner_radius=10)
        filter_card.pack(fill="x", padx=8, pady=(0, 8))

        row = ctk.CTkFrame(filter_card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=8)

        # File type
        ctk.CTkLabel(
            row,
            text="Type:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#cbd5e1",
        ).pack(side="left", padx=(0, 4))

        self.file_type_menu = ctk.CTkOptionMenu(
            row,
            values=[".pdf", ".epub", ".docx", ".zip", "All Files"],
            width=90,
            height=30,
            font=ctk.CTkFont(size=11),
        )
        self.file_type_menu.set(self.config_manager.config.default_extension)
        self.file_type_menu.pack(side="left", padx=(0, 14))

        # Regex / Wildcard Pattern
        ctk.CTkLabel(
            row,
            text="Pattern / Regex:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#cbd5e1",
        ).pack(side="left", padx=(0, 4))

        self.pattern_entry = ctk.CTkEntry(
            row,
            placeholder_text="e.g. Prefix_.*\\.pdf or Report_*",
            width=190,
            height=30,
            font=ctk.CTkFont(size=11),
        )
        self.pattern_entry.pack(side="left", padx=(0, 14))

        # Date Filter
        self.date_filter_var = ctk.BooleanVar(value=False)
        self.date_filter_cb = ctk.CTkCheckBox(
            row,
            text="Date Range:",
            variable=self.date_filter_var,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_toggle_date_filter,
            width=90,
        )
        self.date_filter_cb.pack(side="left", padx=(0, 6))

        self.start_date_entry = ctk.CTkEntry(
            row,
            placeholder_text="YYYY-MM-DD",
            width=95,
            height=30,
            font=ctk.CTkFont(size=11),
            state="disabled",
        )
        self.start_date_entry.pack(side="left", padx=(0, 4))

        ctk.CTkLabel(row, text="to", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left", padx=(0, 4))

        self.end_date_entry = ctk.CTkEntry(
            row,
            placeholder_text="YYYY-MM-DD",
            width=95,
            height=30,
            font=ctk.CTkFont(size=11),
            state="disabled",
        )
        self.end_date_entry.pack(side="left", padx=(0, 14))

        # Scan Limit
        ctk.CTkLabel(
            row,
            text="Scan Limit:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#cbd5e1",
        ).pack(side="left", padx=(0, 4))

        self.limit_menu = ctk.CTkOptionMenu(
            row,
            values=["500 Messages", "1000 Messages", "2000 Messages", "5000 Messages", "All Messages"],
            width=130,
            height=30,
            font=ctk.CTkFont(size=11),
        )
        self.limit_menu.set("1000 Messages")
        self.limit_menu.pack(side="left")

    def _build_table_section(self, parent):
        self.table_view = FilePreviewTable(
            parent,
            on_selection_changed=self._update_download_button_state,
        )
        self.table_view.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_export_section(self, parent):
        export_card = ctk.CTkFrame(parent, fg_color="#182234", corner_radius=10)
        export_card.pack(fill="x", padx=8, pady=(0, 4))

        # Row 1: Output Directory Picker
        row1 = ctk.CTkFrame(export_card, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            row1,
            text="Export Destination:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#cbd5e1",
            width=130,
            anchor="w",
        ).pack(side="left")

        self.dir_entry = ctk.CTkEntry(row1, height=32, font=ctk.CTkFont(size=11))
        self.dir_entry.insert(0, self.config_manager.config.download_dir or get_default_export_dir())
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_btn = ctk.CTkButton(
            row1,
            text="📁 Browse...",
            width=90,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._on_browse_dir,
        )
        browse_btn.pack(side="left", padx=(0, 6))

        open_folder_btn = ctk.CTkButton(
            row1,
            text="Open Folder",
            width=90,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._on_open_export_dir,
        )
        open_folder_btn.pack(side="left")

        # Row 2: ZIP Checkbox & Action Buttons
        row2 = ctk.CTkFrame(export_card, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 6))

        self.zip_var = ctk.BooleanVar(value=self.config_manager.config.compress_to_zip)
        self.zip_cb = ctk.CTkCheckBox(
            row2,
            text="Compress directly into ZIP archive ({Channel}_export_{timestamp}.zip)",
            variable=self.zip_var,
            font=ctk.CTkFont(size=11),
        )
        self.zip_cb.pack(side="left")

        self.cancel_download_btn = ctk.CTkButton(
            row2,
            text="⏹ Cancel",
            width=80,
            height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#ef4444",
            hover_color="#dc2626",
            state="disabled",
            command=self._on_cancel_download,
        )
        self.cancel_download_btn.pack(side="right", padx=(8, 0))

        self.download_btn = ctk.CTkButton(
            row2,
            text="📥 Start Download (0 files)",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._on_start_download,
        )
        self.download_btn.pack(side="right")

        # Row 3: Progress Bar
        self.progress_bar = DualProgressBar(export_card)
        self.progress_bar.pack(fill="x", padx=12, pady=(0, 8))

    def _build_log_section(self):
        """Unified activity log console visible at the bottom of the app."""
        self.log_viewer = LogViewer(self.main_container, height=110)
        self.log_viewer.pack(fill="x", padx=12, pady=(0, 8))

    # -------------------------------------------------------------
    # Auth & Startup
    # -------------------------------------------------------------

    def _check_initial_auth(self):
        """Attempts to auto-connect using saved credentials in background."""
        self.status_badge.set_status("Checking session...", "connecting")

        def worker():
            is_auth, user_name = self.backend.check_saved_session()
            
            def on_ui():
                if is_auth:
                    self.status_badge.set_status(f"Connected: {user_name}", "connected")
                    self.log(f"Auto-connected to Telegram as {user_name}.")
                else:
                    self.status_badge.set_status("Disconnected", "disconnected")
                    self.log("Telegram client: Not logged in. Click 'Login / API Settings' to authenticate.")

            self.after(0, on_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _open_auth_modal(self):
        AuthModal(
            self,
            backend=self.backend,
            config_manager=self.config_manager,
            on_login_success=self._on_login_success,
        )

    def _on_login_success(self, message: str):
        self.log(f"Authentication success: {message}")
        user_name = "Telegram User"
        if self.backend._current_user:
            user_name = self.backend._current_user.first_name or self.backend._current_user.username or user_name
        self.status_badge.set_status(f"Connected: {user_name}", "connected")

    def _on_logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to log out and clear saved credentials?"):
            success, msg = self.backend.log_out()
            self.status_badge.set_status("Disconnected", "disconnected")
            self.log(msg)
            messagebox.showinfo("Logout", msg)

    # -------------------------------------------------------------
    # Channel Verification & Fetching
    # -------------------------------------------------------------

    def _on_verify_channel(self):
        channel_input = self.channel_entry.get().strip()
        if not channel_input:
            messagebox.showwarning("Channel Required", "Please enter a Telegram channel username, invite link, or ID.")
            return

        self.verify_btn.configure(state="disabled")
        self.channel_info_lbl.configure(text="Verifying channel access...", text_color="#38bdf8")

        def worker():
            success, info, msg = self.backend.resolve_channel(channel_input)

            def on_ui():
                self.verify_btn.configure(state="normal")
                if success and info:
                    self.verified_channel = info
                    members_txt = f" • {info.participants_count:,} members" if info.participants_count else ""
                    self.channel_info_lbl.configure(
                        text=f"✔ Verified: {info.display_name}{members_txt}",
                        text_color="#34d399",
                    )
                    self.log(f"Channel verified: {info.display_name}")
                    # Save last channel in config
                    cfg = self.config_manager.config
                    cfg.last_channel = channel_input
                    self.config_manager.save(cfg)
                else:
                    self.verified_channel = None
                    self.channel_info_lbl.configure(text=f"✖ {msg}", text_color="#f87171")
                    self.log(f"Verification error: {msg}")

            self.after(0, on_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _on_start_fetch(self):
        if self.is_scanning:
            return

        channel_input = self.channel_entry.get().strip()
        if not channel_input:
            messagebox.showwarning("Channel Required", "Please enter a target channel to scan.")
            return

        pattern = self.pattern_entry.get().strip()
        if pattern:
            valid, err = is_valid_regex(pattern)
            if not valid:
                messagebox.showerror("Regex Error", f"Invalid regex pattern:\n{err}")
                return

        # Date range parsing
        date_from = None
        date_to = None
        if self.date_filter_var.get():
            from_str = self.start_date_entry.get().strip()
            to_str = self.end_date_entry.get().strip()
            if from_str:
                date_from = parse_date_str(from_str)
                if not date_from:
                    messagebox.showerror("Date Error", "Invalid Start Date format. Use YYYY-MM-DD.")
                    return
            if to_str:
                date_to = parse_date_str(to_str)
                if not date_to:
                    messagebox.showerror("Date Error", "Invalid End Date format. Use YYYY-MM-DD.")
                    return

        # Parse limit
        limit_text = self.limit_menu.get()
        limit_val = 1000
        if "500" in limit_text:
            limit_val = 500
        elif "1000" in limit_text:
            limit_val = 1000
        elif "2000" in limit_text:
            limit_val = 2000
        elif "5000" in limit_text:
            limit_val = 5000
        elif "All" in limit_text:
            limit_val = 0

        # UI State update
        self.is_scanning = True
        self.scan_cancel_event.clear()
        self.fetch_btn.configure(state="disabled")
        self.stop_fetch_btn.configure(state="normal")
        self.table_view.clear()
        self._update_download_button_state()

        file_ext = self.file_type_menu.get()

        def batch_cb(files_batch, scanned_total, matched_total):
            def update():
                self.table_view.add_files(files_batch)
                self.channel_info_lbl.configure(
                    text=f"Scanning... Scanned {scanned_total} messages | Found {matched_total} matching files.",
                    text_color="#38bdf8",
                )
                self._update_download_button_state()
            self.after(0, update)

        def log_cb(msg):
            self.after(0, lambda: self.log(msg))

        def worker():
            try:
                self.backend.fetch_files_stream(
                    channel_input=channel_input,
                    file_extension=file_ext,
                    pattern=pattern,
                    date_from=date_from,
                    date_to=date_to,
                    limit=limit_val,
                    batch_callback=batch_cb,
                    log_callback=log_cb,
                    cancel_event=self.scan_cancel_event,
                ).result()
            except Exception as e:
                self.after(0, lambda: self.log(f"Scan aborted: {str(e)}"))
            finally:
                def on_done():
                    self.is_scanning = False
                    self.fetch_btn.configure(state="normal")
                    self.stop_fetch_btn.configure(state="disabled")
                    self._update_download_button_state()
                self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_stop_fetch(self):
        if self.is_scanning:
            self.scan_cancel_event.set()
            self.log("Stopping scan...")

    def _on_toggle_date_filter(self):
        state = "normal" if self.date_filter_var.get() else "disabled"
        self.start_date_entry.configure(state=state)
        self.end_date_entry.configure(state=state)

    # -------------------------------------------------------------
    # Download Pipeline
    # -------------------------------------------------------------

    def _update_download_button_state(self):
        selected = self.table_view.get_selected_files()
        count = len(selected)
        total_size = sum(f.file_size for f in selected)
        size_txt = f" ({format_bytes(total_size)})" if count > 0 else ""
        self.download_btn.configure(text=f"📥 Start Download ({count} files{size_txt})")
        if count > 0 and not self.is_downloading:
            self.download_btn.configure(state="normal")
        else:
            if not self.is_downloading:
                self.download_btn.configure(state="disabled")

    def _on_browse_dir(self):
        path = filedialog.askdirectory(initialdir=self.dir_entry.get().strip() or get_default_export_dir())
        if path:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, path)
            cfg = self.config_manager.config
            cfg.download_dir = path
            self.config_manager.save(cfg)

    def _on_open_export_dir(self):
        target = self.dir_entry.get().strip()
        if os.path.exists(target):
            try:
                os.startfile(target)
            except Exception:
                subprocess.Popen(["explorer", target])
        else:
            messagebox.showinfo("Folder Not Found", "The destination folder does not exist yet.")

    def _on_start_download(self):
        selected_files = self.table_view.get_selected_files()
        if not selected_files:
            messagebox.showwarning("No Selection", "Please select at least one file to download.")
            return

        out_dir = self.dir_entry.get().strip()
        if not out_dir:
            out_dir = get_default_export_dir()
            self.dir_entry.insert(0, out_dir)

        compress_zip = self.zip_var.get()

        # Update UI states
        self.is_downloading = True
        self.download_btn.configure(state="disabled")
        self.cancel_download_btn.configure(state="normal")
        self.progress_bar.reset()

        def prog_cb(progress: DownloadProgress):
            def update():
                overall_frac = progress.overall_percent
                overall_txt = f"Overall Progress: {progress.current_file_index} / {progress.total_files} files ({format_bytes(progress.total_bytes_downloaded)} / {format_bytes(progress.total_bytes_all)})"
                file_frac = progress.current_file_percent
                file_txt = f"Current: {progress.current_file_name} ({format_bytes(progress.current_file_downloaded)} / {format_bytes(progress.current_file_total)})"
                speed_txt = progress.formatted_speed if progress.speed_bps > 0 else ""

                if progress.is_waiting_flood:
                    file_txt = f"⏳ Flood Wait: Resuming in {progress.flood_wait_seconds}s..."

                self.progress_bar.update_progress(
                    overall_frac=overall_frac,
                    overall_text=overall_txt,
                    file_frac=file_frac,
                    file_text=file_txt,
                    speed_text=speed_txt,
                )
            self.after(0, update)

        def log_cb(msg: str):
            self.after(0, lambda: self.log(msg))

        def on_complete(success: bool, msg: str, final_path: Optional[str]):
            def update():
                self.is_downloading = False
                self.cancel_download_btn.configure(state="disabled")
                self._update_download_button_state()
                if success:
                    self.log(f"🎉 Download complete! Saved to: {final_path}")
                    if messagebox.askyesno("Download Complete", f"{msg}\n\nWould you like to open the export folder?"):
                        folder_to_open = os.path.dirname(final_path) if final_path and final_path.endswith(".zip") else final_path
                        if folder_to_open and os.path.exists(folder_to_open):
                            os.startfile(folder_to_open)
                else:
                    self.log(f"Download stopped: {msg}")
            self.after(0, update)

        def worker():
            try:
                self.downloader.start_download(
                    files=selected_files,
                    output_dir=out_dir,
                    compress_to_zip=compress_zip,
                    progress_callback=prog_cb,
                    log_callback=log_cb,
                    on_complete_callback=on_complete,
                ).result()
            except Exception as e:
                self.after(0, lambda: self.log(f"Download error: {str(e)}"))
                self.after(0, lambda: self._on_download_finished_cleanup())

        threading.Thread(target=worker, daemon=True).start()

    def _on_cancel_download(self):
        if self.is_downloading:
            self.downloader.cancel()
            self.log("Cancelling download...")

    def _on_download_finished_cleanup(self):
        self.is_downloading = False
        self.cancel_download_btn.configure(state="disabled")
        self._update_download_button_state()

    def log(self, message: str):
        self.log_viewer.log(message)


def main():
    app = TeleFetchApp()
    app.mainloop()


if __name__ == "__main__":
    main()
