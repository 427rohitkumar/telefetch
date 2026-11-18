"""
Tab 2: PDF Split & Master Merger GUI Component.
Allows selecting up to 100 PDFs, slicing up to N pages from each, and assembling them
into a sequential Master Merged PDF.
"""

import os
import subprocess
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional
import customtkinter as ctk

import natsort
from src.models import MergeProgress, PDFFileInfo
from src.pdf_merger import PDFMerger, inspect_pdf_file
from src.utils import format_bytes, get_default_export_dir


class PDFMergerTab(ctk.CTkFrame):
    """
    GUI Frame for PDF Slicing and Master PDF Merging.
    """

    MAX_PDF_LIMIT = 100

    def __init__(self, master, log_callback=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.log_callback = log_callback

        self.merger = PDFMerger()
        self.pdf_files: Dict[str, PDFFileInfo] = {}
        self.is_processing = False
        self.last_merged_output: Optional[str] = None
        self.input_folder_hint: Optional[str] = None

        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "PDFMerger.Treeview",
            background="#0f172a",
            foreground="#f8fafc",
            fieldbackground="#0f172a",
            rowheight=28,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        style.map(
            "PDFMerger.Treeview",
            background=[("selected", "#0369a1")],
            foreground=[("selected", "#ffffff")],
        )

        style.configure(
            "PDFMerger.Treeview.Heading",
            background="#1e293b",
            foreground="#94a3b8",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padding=(6, 6),
        )
        style.map(
            "PDFMerger.Treeview.Heading",
            background=[("active", "#334155")],
            foreground=[("active", "#f8fafc")],
        )

    def _build_ui(self):
        # ---------------------------------------------------------
        # 1. Top Section: Input Selection Bar & Actions
        # ---------------------------------------------------------
        top_card = ctk.CTkFrame(self, fg_color="#182234", corner_radius=10)
        top_card.pack(fill="x", padx=12, pady=(10, 8))

        top_row = ctk.CTkFrame(top_card, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=10)

        # File Selection Buttons
        self.select_folder_btn = ctk.CTkButton(
            top_row,
            text="📁 Select Folder",
            width=130,
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._on_select_folder,
        )
        self.select_folder_btn.pack(side="left", padx=(0, 8))

        self.select_files_btn = ctk.CTkButton(
            top_row,
            text="📄 Select PDF Files",
            width=140,
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self._on_select_files,
        )
        self.select_files_btn.pack(side="left", padx=(0, 16))

        # List Management
        self.remove_btn = ctk.CTkButton(
            top_row,
            text="❌ Remove Selected",
            width=130,
            height=34,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._on_remove_selected,
        )
        self.remove_btn.pack(side="left", padx=(0, 8))

        self.clear_all_btn = ctk.CTkButton(
            top_row,
            text="🗑 Clear All",
            width=100,
            height=34,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._on_clear_all,
        )
        self.clear_all_btn.pack(side="left")

        # Limit badge
        limit_lbl = ctk.CTkLabel(
            top_row,
            text=f"Max Limit: {self.MAX_PDF_LIMIT} PDFs",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        )
        limit_lbl.pack(side="right", padx=4)

        # ---------------------------------------------------------
        # 2. Middle Section: PDF Table Preview
        # ---------------------------------------------------------
        table_card = ctk.CTkFrame(self, fg_color="#182234", corner_radius=10)
        table_card.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        table_container = ctk.CTkFrame(table_card, fg_color="#0f172a", corner_radius=6)
        table_container.pack(fill="both", expand=True, padx=10, pady=(10, 4))

        columns = ("filename", "pages", "size", "path")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            style="PDFMerger.Treeview",
            selectmode="extended",
        )

        self.tree.heading("filename", text="PDF File Name (Natural Order ⬍)")
        self.tree.heading("pages", text="Pages ⬍")
        self.tree.heading("size", text="Size ⬍")
        self.tree.heading("path", text="Source Path")

        self.tree.column("filename", width=340, anchor="w")
        self.tree.column("pages", width=90, anchor="center")
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("path", width=420, anchor="w")

        v_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Bottom stats row of table
        stats_row = ctk.CTkFrame(table_card, fg_color="transparent")
        stats_row.pack(fill="x", padx=12, pady=(4, 8))

        self.stats_label = ctk.CTkLabel(
            stats_row,
            text="No PDF files selected yet. Click 'Select Folder' or 'Select PDF Files' to add up to 100 PDFs.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        )
        self.stats_label.pack(side="left")

        # ---------------------------------------------------------
        # 3. Settings Card: Slicing & Master Output Settings
        # ---------------------------------------------------------
        settings_card = ctk.CTkFrame(self, fg_color="#182234", corner_radius=10)
        settings_card.pack(fill="x", padx=12, pady=(0, 8))

        # Row 1: Slicing configuration
        slicing_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        slicing_row.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            slicing_row,
            text="Pages to Extract:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e2e8f0",
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            slicing_row,
            text="Extract first",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        ).pack(side="left", padx=(0, 6))

        self.pages_spinbox = ctk.CTkEntry(
            slicing_row,
            width=65,
            height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            justify="center",
        )
        self.pages_spinbox.insert(0, "30")
        self.pages_spinbox.pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            slicing_row,
            text="pages from each PDF (If a PDF has fewer pages, all available pages are extracted).",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        ).pack(side="left")

        # Row 2: Master Output File Configuration
        output_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        output_row.pack(fill="x", padx=12, pady=(4, 4))

        ctk.CTkLabel(
            output_row,
            text="Master File Name:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#cbd5e1",
            width=120,
            anchor="w",
        ).pack(side="left")

        self.master_name_entry = ctk.CTkEntry(
            output_row,
            width=220,
            height=30,
            font=ctk.CTkFont(size=11),
        )
        self.master_name_entry.insert(0, "Master_Merged.pdf")
        self.master_name_entry.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            output_row,
            text="Output Folder:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#cbd5e1",
            width=100,
            anchor="w",
        ).pack(side="left")

        self.out_dir_entry = ctk.CTkEntry(
            output_row,
            height=30,
            font=ctk.CTkFont(size=11),
        )
        default_dir = os.path.join(get_default_export_dir(), "PDF_Merged")
        self.out_dir_entry.insert(0, default_dir)
        self.out_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_out_btn = ctk.CTkButton(
            output_row,
            text="📁 Browse...",
            width=85,
            height=30,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._on_browse_output_dir,
        )
        browse_out_btn.pack(side="left")

        # Row 3: Quick Auto-fill destination buttons
        quick_btn_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        quick_btn_row.pack(fill="x", padx=12, pady=(0, 8))

        use_downloads_btn = ctk.CTkButton(
            quick_btn_row,
            text="Use Downloads Folder",
            height=24,
            font=ctk.CTkFont(size=10),
            fg_color="#1e293b",
            hover_color="#334155",
            command=self._on_use_downloads_folder,
        )
        use_downloads_btn.pack(side="left", padx=(120, 8))

        same_as_input_btn = ctk.CTkButton(
            quick_btn_row,
            text="Same as Input Folder",
            height=24,
            font=ctk.CTkFont(size=10),
            fg_color="#1e293b",
            hover_color="#334155",
            command=self._on_use_input_folder,
        )
        same_as_input_btn.pack(side="left")

        # ---------------------------------------------------------
        # 4. Action & Progress Section
        # ---------------------------------------------------------
        action_card = ctk.CTkFrame(self, fg_color="#182234", corner_radius=10)
        action_card.pack(fill="x", padx=12, pady=(0, 10))

        action_row = ctk.CTkFrame(action_card, fg_color="transparent")
        action_row.pack(fill="x", padx=12, pady=(10, 6))

        self.start_merge_btn = ctk.CTkButton(
            action_row,
            text="🚀 Start Slicing & Merge Master PDF",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            fg_color="#10b981",
            hover_color="#059669",
            command=self._on_start_merge,
        )
        self.start_merge_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.cancel_btn = ctk.CTkButton(
            action_row,
            text="⏹ Cancel",
            width=85,
            height=38,
            font=ctk.CTkFont(size=12),
            fg_color="#ef4444",
            hover_color="#dc2626",
            state="disabled",
            command=self._on_cancel,
        )
        self.cancel_btn.pack(side="left", padx=(0, 8))

        self.open_folder_btn = ctk.CTkButton(
            action_row,
            text="📂 Open Folder",
            width=105,
            height=38,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            state="disabled",
            command=self._on_open_output_folder,
        )
        self.open_folder_btn.pack(side="left")

        # Progress bar & status
        prog_header = ctk.CTkFrame(action_card, fg_color="transparent")
        prog_header.pack(fill="x", padx=12, pady=(2, 2))

        self.prog_status_lbl = ctk.CTkLabel(
            prog_header,
            text="Ready. Select files and click 'Start Slicing & Merge'.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        )
        self.prog_status_lbl.pack(side="left")

        self.prog_pct_lbl = ctk.CTkLabel(
            prog_header,
            text="0%",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8",
        )
        self.prog_pct_lbl.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            action_card,
            orientation="horizontal",
            mode="determinate",
            progress_color="#10b981",
            fg_color="#334155",
            height=8,
        )
        self.progress_bar.pack(fill="x", padx=12, pady=(2, 10))
        self.progress_bar.set(0)

    # -------------------------------------------------------------
    # File Input Handlers
    # -------------------------------------------------------------

    def _on_select_folder(self):
        folder_path = filedialog.askdirectory(title="Select Folder Containing PDFs")
        if not folder_path:
            return

        self.input_folder_hint = folder_path
        # Auto set output path if default
        if not self.out_dir_entry.get().strip():
            self.out_dir_entry.insert(0, folder_path)

        # Scan for PDFs
        candidates = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(".pdf"):
                    candidates.append(os.path.join(root, file))

        if not candidates:
            messagebox.showinfo("No PDFs Found", f"No PDF files were found in:\n{folder_path}")
            return

        sorted_paths = natsort.natsorted(candidates)
        self._add_files_from_paths(sorted_paths)

    def _on_select_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Select PDF Files (Up to 100)",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if not file_paths:
            return

        if file_paths:
            self.input_folder_hint = os.path.dirname(file_paths[0])

        sorted_paths = natsort.natsorted(list(file_paths))
        self._add_files_from_paths(sorted_paths)

    def _add_files_from_paths(self, file_paths: List[str]):
        """Inspects and loads PDF files, respecting the 100 files limit."""
        added_count = 0
        current_count = len(self.pdf_files)
        overflow_warned = False

        for f_path in file_paths:
            if current_count >= self.MAX_PDF_LIMIT:
                if not overflow_warned:
                    messagebox.showwarning(
                        "Limit Reached",
                        f"Maximum limit of {self.MAX_PDF_LIMIT} PDFs reached. Additional files were not added.",
                    )
                    overflow_warned = True
                break

            if f_path in self.pdf_files:
                continue

            info = inspect_pdf_file(f_path)
            if info:
                self.pdf_files[f_path] = info
                current_count += 1
                added_count += 1

        self._refresh_table()
        if self.log_callback and added_count > 0:
            self.log_callback(f"[PDF Merger] Added {added_count} files (Total: {len(self.pdf_files)}/{self.MAX_PDF_LIMIT})")

    def _refresh_table(self):
        """Clears and re-populates table sorted by natural filename order."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        sorted_items = natsort.natsorted(self.pdf_files.values(), key=lambda f: f.file_name)
        total_pages = 0
        total_bytes = 0

        for f in sorted_items:
            total_pages += f.page_count
            total_bytes += f.file_size
            self.tree.insert(
                "",
                "end",
                iid=f.path,
                values=(
                    f.file_name,
                    f"{f.page_count} pages",
                    f.formatted_size,
                    f.path,
                ),
            )

        count = len(self.pdf_files)
        if count == 0:
            self.stats_label.configure(
                text="No PDF files selected yet. Click 'Select Folder' or 'Select PDF Files' to add up to 100 PDFs.",
                text_color="#94a3b8",
            )
        else:
            self.stats_label.configure(
                text=f"Total: {count}/{self.MAX_PDF_LIMIT} PDFs  |  Combined Pages: {total_pages:,}  |  Total Size: {format_bytes(total_bytes)}",
                text_color="#38bdf8",
            )

    def _on_remove_selected(self):
        selected_iids = self.tree.selection()
        if not selected_iids:
            return
        for iid in selected_iids:
            if iid in self.pdf_files:
                del self.pdf_files[iid]
        self._refresh_table()

    def _on_clear_all(self):
        self.pdf_files.clear()
        self._refresh_table()

    # -------------------------------------------------------------
    # Output Folder Helpers
    # -------------------------------------------------------------

    def _on_browse_output_dir(self):
        folder = filedialog.askdirectory(initialdir=self.out_dir_entry.get().strip() or get_default_export_dir())
        if folder:
            self.out_dir_entry.delete(0, "end")
            self.out_dir_entry.insert(0, folder)

    def _on_use_downloads_folder(self):
        down_dir = os.path.join(get_default_export_dir(), "PDF_Merged")
        self.out_dir_entry.delete(0, "end")
        self.out_dir_entry.insert(0, down_dir)

    def _on_use_input_folder(self):
        if self.input_folder_hint and os.path.isdir(self.input_folder_hint):
            self.out_dir_entry.delete(0, "end")
            self.out_dir_entry.insert(0, self.input_folder_hint)
        elif self.pdf_files:
            first_path = next(iter(self.pdf_files.keys()))
            first_dir = os.path.dirname(first_path)
            self.out_dir_entry.delete(0, "end")
            self.out_dir_entry.insert(0, first_dir)
        else:
            messagebox.showinfo("Input Folder", "Please select input files or folder first.")

    def _on_open_output_folder(self):
        if self.last_merged_output and os.path.exists(self.last_merged_output):
            out_folder = os.path.dirname(self.last_merged_output)
            try:
                os.startfile(out_folder)
            except Exception:
                subprocess.Popen(["explorer", out_folder])
        else:
            out_dir = self.out_dir_entry.get().strip()
            if os.path.exists(out_dir):
                try:
                    os.startfile(out_dir)
                except Exception:
                    subprocess.Popen(["explorer", out_dir])

    # -------------------------------------------------------------
    # Slicing & Merge Execution
    # -------------------------------------------------------------

    def _on_start_merge(self):
        if self.is_processing:
            return

        if not self.pdf_files:
            messagebox.showwarning("No Files", "Please add at least one PDF file to merge.")
            return

        # Validate pages to extract
        pages_str = self.pages_spinbox.get().strip()
        if not pages_str.isdigit() or int(pages_str) <= 0:
            messagebox.showerror("Invalid Input", "Please enter a valid positive number for pages to extract (e.g. 30).")
            return
        pages_to_extract = int(pages_str)

        # Validate master filename
        master_name = self.master_name_entry.get().strip()
        if not master_name:
            master_name = "Master_Merged.pdf"
        if not master_name.lower().endswith(".pdf"):
            master_name += ".pdf"

        # Validate output directory
        out_dir = self.out_dir_entry.get().strip()
        if not out_dir:
            out_dir = os.path.join(get_default_export_dir(), "PDF_Merged")
            self.out_dir_entry.delete(0, "end")
            self.out_dir_entry.insert(0, out_dir)

        output_full_path = os.path.join(out_dir, master_name)

        # UI state updates
        self.merger.cancel_event.clear()
        self.is_processing = True
        self.start_merge_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.select_folder_btn.configure(state="disabled")
        self.select_files_btn.configure(state="disabled")
        self.remove_btn.configure(state="disabled")
        self.clear_all_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.prog_pct_lbl.configure(text="0%")
        self.prog_status_lbl.configure(text="Starting merge process...", text_color="#38bdf8")

        files_list = list(self.pdf_files.values())

        def prog_cb(prog: MergeProgress):
            def update():
                frac = prog.overall_percent
                self.progress_bar.set(frac)
                self.prog_pct_lbl.configure(text=f"{int(frac * 100)}%")
                self.prog_status_lbl.configure(text=prog.status_text, text_color="#38bdf8")
            self.after(0, update)

        def log_cb(msg: str):
            if self.log_callback:
                self.after(0, lambda: self.log_callback(f"[PDF Merger] {msg}"))

        def worker():
            success, msg, final_path = self.merger.process_and_merge(
                files=files_list,
                output_path=output_full_path,
                pages_to_extract=pages_to_extract,
                progress_callback=prog_cb,
                log_callback=log_cb,
            )

            def on_done():
                self.is_processing = False
                self.start_merge_btn.configure(state="normal")
                self.cancel_btn.configure(state="disabled")
                self.select_folder_btn.configure(state="normal")
                self.select_files_btn.configure(state="normal")
                self.remove_btn.configure(state="normal")
                self.clear_all_btn.configure(state="normal")

                if success and final_path:
                    self.last_merged_output = final_path
                    self.open_folder_btn.configure(state="normal")
                    self.progress_bar.set(1.0)
                    self.prog_pct_lbl.configure(text="100%")
                    self.prog_status_lbl.configure(text=f"Master PDF created: {os.path.basename(final_path)}", text_color="#34d399")

                    # Pop-up message with direct open option
                    if messagebox.askyesno(
                        "Master PDF Created",
                        f"{msg}\n\nLocation: {final_path}\n\nWould you like to open the output folder now?",
                    ):
                        self._on_open_output_folder()
                else:
                    self.prog_status_lbl.configure(text=f"Process ended: {msg}", text_color="#f87171")

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_cancel(self):
        if self.is_processing:
            self.merger.cancel()
            self.prog_status_lbl.configure(text="Cancelling operation...", text_color="#f59e0b")
