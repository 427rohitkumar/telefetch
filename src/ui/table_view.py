"""
Interactive Preview Table for TeleFetch using themed ttk.Treeview embedded inside CustomTkinter.
Supports check-boxes, multi-select, column sorting, search filtering, and live selection statistics.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional
import customtkinter as ctk

from src.models import TelegramFileInfo
from src.utils import format_bytes


class FilePreviewTable(ctk.CTkFrame):
    """
    High-performance data table for browsing scanned Telegram files with selection toggles.
    """

    def __init__(self, master, on_selection_changed: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(master, fg_color="#182234", corner_radius=10, **kwargs)
        self.on_selection_changed = on_selection_changed

        self.files_map: Dict[str, TelegramFileInfo] = {}
        self.displayed_items: List[str] = []
        self._sort_reverse: Dict[str, bool] = {}

        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Configure dark colors matching CustomTkinter
        style.configure(
            "TeleFetch.Treeview",
            background="#0f172a",
            foreground="#f8fafc",
            fieldbackground="#0f172a",
            rowheight=28,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        style.map(
            "TeleFetch.Treeview",
            background=[("selected", "#0369a1")],
            foreground=[("selected", "#ffffff")],
        )

        style.configure(
            "TeleFetch.Treeview.Heading",
            background="#1e293b",
            foreground="#94a3b8",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padding=(6, 6),
        )
        style.map(
            "TeleFetch.Treeview.Heading",
            background=[("active", "#334155")],
            foreground=[("active", "#f8fafc")],
        )

    def _build_ui(self):
        # Action & Filter Bar above table
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(8, 4))

        self.select_all_btn = ctk.CTkButton(
            top_bar,
            text="✓ Select All",
            width=90,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self.select_all,
        )
        self.select_all_btn.pack(side="left", padx=(0, 6))

        self.deselect_all_btn = ctk.CTkButton(
            top_bar,
            text="✗ Deselect All",
            width=95,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self.deselect_all,
        )
        self.deselect_all_btn.pack(side="left", padx=(0, 6))

        self.invert_btn = ctk.CTkButton(
            top_bar,
            text="⇄ Invert",
            width=70,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self.invert_selection,
        )
        self.invert_btn.pack(side="left", padx=(0, 10))

        # Quick search filter entry
        self.search_entry = ctk.CTkEntry(
            top_bar,
            placeholder_text="Quick search in results...",
            height=28,
            font=ctk.CTkFont(size=11),
            width=200,
        )
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_quick_search())

        # Table & Scrollbar container
        table_container = tk.Frame(self, bg="#0f172a")
        table_container.pack(fill="both", expand=True, padx=10, pady=(4, 6))

        columns = ("select", "filename", "size", "date", "msg_id")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            style="TeleFetch.Treeview",
            selectmode="extended",
        )

        self.tree.heading("select", text="[✓] Select", command=lambda: self.toggle_master_select())
        self.tree.heading("filename", text="File Name ⬍", command=lambda: self._sort_column("filename"))
        self.tree.heading("size", text="Size ⬍", command=lambda: self._sort_column("size"))
        self.tree.heading("date", text="Upload Date ⬍", command=lambda: self._sort_column("date"))
        self.tree.heading("msg_id", text="Msg ID ⬍", command=lambda: self._sort_column("msg_id"))

        self.tree.column("select", width=80, anchor="center", stretch=False)
        self.tree.column("filename", width=420, anchor="w")
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("date", width=150, anchor="center")
        self.tree.column("msg_id", width=80, anchor="center", stretch=False)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Bindings
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<space>", self._on_tree_space)

        # Bottom stats bar
        stats_bar = ctk.CTkFrame(self, fg_color="transparent")
        stats_bar.pack(fill="x", padx=10, pady=(2, 6))

        self.stats_label = ctk.CTkLabel(
            stats_bar,
            text="No files scanned yet.",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8",
        )
        self.stats_label.pack(side="left")

    def _on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item_id = self.tree.identify_row(event.y)
            if item_id:
                # If clicked specifically on the select column (#1), toggle selection
                if column == "#1":
                    self._toggle_item_selection(item_id)
                    return "break"
                else:
                    # Double click or regular click selects row
                    pass

    def _on_tree_space(self, event):
        selected_items = self.tree.selection()
        if selected_items:
            for item_id in selected_items:
                self._toggle_item_selection(item_id)
            return "break"

    def _toggle_item_selection(self, item_id: str):
        if item_id in self.files_map:
            file_info = self.files_map[item_id]
            file_info.selected = not file_info.selected
            mark = "✔" if file_info.selected else "  "
            current_vals = list(self.tree.item(item_id, "values"))
            current_vals[0] = f"[{mark}]"
            self.tree.item(item_id, values=current_vals)
            self._update_stats()
            if self.on_selection_changed:
                self.on_selection_changed()

    def add_files(self, new_files: List[TelegramFileInfo]):
        """Adds a batch of newly scanned files to the table."""
        for f in new_files:
            item_id = f"msg_{f.message_id}"
            if item_id not in self.files_map:
                self.files_map[item_id] = f
                mark = "✔" if f.selected else "  "
                self.tree.insert(
                    "",
                    "end",
                    iid=item_id,
                    values=(
                        f"[{mark}]",
                        f.file_name,
                        f.formatted_size,
                        f.formatted_date,
                        str(f.message_id),
                    ),
                )
        self._update_stats()

    def clear(self):
        """Clears all records from the table."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.files_map.clear()
        self.search_entry.delete(0, "end")
        self._update_stats()

    def select_all(self):
        for item_id in self.tree.get_children():
            if item_id in self.files_map:
                self.files_map[item_id].selected = True
                current_vals = list(self.tree.item(item_id, "values"))
                current_vals[0] = "[✔]"
                self.tree.item(item_id, values=current_vals)
        self._update_stats()
        if self.on_selection_changed:
            self.on_selection_changed()

    def deselect_all(self):
        for item_id in self.tree.get_children():
            if item_id in self.files_map:
                self.files_map[item_id].selected = False
                current_vals = list(self.tree.item(item_id, "values"))
                current_vals[0] = "[  ]"
                self.tree.item(item_id, values=current_vals)
        self._update_stats()
        if self.on_selection_changed:
            self.on_selection_changed()

    def invert_selection(self):
        for item_id in self.tree.get_children():
            if item_id in self.files_map:
                f = self.files_map[item_id]
                f.selected = not f.selected
                mark = "✔" if f.selected else "  "
                current_vals = list(self.tree.item(item_id, "values"))
                current_vals[0] = f"[{mark}]"
                self.tree.item(item_id, values=current_vals)
        self._update_stats()
        if self.on_selection_changed:
            self.on_selection_changed()

    def toggle_master_select(self):
        # If all currently selected, deselect all, else select all
        all_selected = all(f.selected for f in self.files_map.values()) if self.files_map else False
        if all_selected:
            self.deselect_all()
        else:
            self.select_all()

    def get_selected_files(self) -> List[TelegramFileInfo]:
        """Returns list of all currently checked files."""
        return [f for f in self.files_map.values() if f.selected]

    def get_total_files_count(self) -> int:
        return len(self.files_map)

    def _update_stats(self):
        total_count = len(self.files_map)
        selected_files = self.get_selected_files()
        selected_count = len(selected_files)
        selected_size = sum(f.file_size for f in selected_files)
        total_size = sum(f.file_size for f in self.files_map.values())

        if total_count == 0:
            self.stats_label.configure(text="No files scanned yet.")
        else:
            self.stats_label.configure(
                text=f"Total Found: {total_count} ({format_bytes(total_size)})  |  Selected: {selected_count} ({format_bytes(selected_size)})"
            )

    def _on_quick_search(self):
        query = self.search_entry.get().strip().lower()
        for item_id, f in self.files_map.items():
            if not query or query in f.file_name.lower():
                if not self.tree.exists(item_id):
                    mark = "✔" if f.selected else "  "
                    self.tree.insert(
                        "",
                        "end",
                        iid=item_id,
                        values=(f"[{mark}]", f.file_name, f.formatted_size, f.formatted_date, str(f.message_id)),
                    )
            else:
                if self.tree.exists(item_id):
                    self.tree.delete(item_id)

    def _sort_column(self, col: str):
        reverse = self._sort_reverse.get(col, False)
        self._sort_reverse[col] = not reverse

        items = list(self.files_map.items())
        if col == "filename":
            items.sort(key=lambda x: x[1].file_name.lower(), reverse=reverse)
        elif col == "size":
            items.sort(key=lambda x: x[1].file_size, reverse=reverse)
        elif col == "date":
            items.sort(key=lambda x: x[1].date, reverse=reverse)
        elif col == "msg_id":
            items.sort(key=lambda x: x[1].message_id, reverse=reverse)

        for idx, (item_id, _) in enumerate(items):
            if self.tree.exists(item_id):
                self.tree.move(item_id, "", idx)
