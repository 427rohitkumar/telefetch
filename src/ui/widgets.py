"""
Custom reusable UI components for TeleFetch: Status badges, Log viewer, Progress trackers.
"""

import tkinter as tk
from datetime import datetime
from typing import Optional
import customtkinter as ctk


class StatusBadge(ctk.CTkFrame):
    """Visual status pill badge with color dot and text."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#1e293b", corner_radius=16, height=32, **kwargs)
        
        self.dot = ctk.CTkLabel(
            self,
            text="●",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ef4444",
            width=16,
        )
        self.dot.pack(side="left", padx=(10, 4), pady=4)

        self.label = ctk.CTkLabel(
            self,
            text="Disconnected",
            font=ctk.CTkFont(size=12, weight="normal"),
            text_color="#cbd5e1",
        )
        self.label.pack(side="left", padx=(0, 12), pady=4)

    def set_status(self, text: str, state: str = "disconnected"):
        """Sets status text and dot color ('connected', 'connecting', 'disconnected', 'warning')."""
        colors = {
            "connected": "#10b981",    # Emerald green
            "connecting": "#3b82f6",   # Blue
            "warning": "#f59e0b",      # Amber
            "disconnected": "#ef4444", # Red
        }
        color = colors.get(state, "#94a3b8")
        self.dot.configure(text_color=color)
        self.label.configure(text=text)


class StatCard(ctk.CTkFrame):
    """Compact metric card displaying count and label."""

    def __init__(self, master, label: str, value: str = "0", **kwargs):
        super().__init__(master, fg_color="#1e293b", corner_radius=8, **kwargs)
        
        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#38bdf8",
        )
        self.value_label.pack(padx=12, pady=(6, 0))

        self.title_label = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        )
        self.title_label.pack(padx=12, pady=(0, 6))

    def set_value(self, val: str):
        self.value_label.configure(text=val)


class DualProgressBar(ctk.CTkFrame):
    """Displays overall download progress and individual file progress with speed."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#182234", corner_radius=10, **kwargs)

        # Overall progress row
        self.overall_header = ctk.CTkFrame(self, fg_color="transparent")
        self.overall_header.pack(fill="x", padx=12, pady=(8, 2))

        self.overall_title = ctk.CTkLabel(
            self.overall_header,
            text="Overall Progress: 0 / 0 files",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e2e8f0",
        )
        self.overall_title.pack(side="left")

        self.overall_percent_lbl = ctk.CTkLabel(
            self.overall_header,
            text="0%",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8",
        )
        self.overall_percent_lbl.pack(side="right")

        self.overall_bar = ctk.CTkProgressBar(
            self,
            orientation="horizontal",
            mode="determinate",
            progress_color="#0284c7",
            fg_color="#334155",
            height=10,
        )
        self.overall_bar.pack(fill="x", padx=12, pady=(2, 8))
        self.overall_bar.set(0)

        # Current file progress row
        self.file_header = ctk.CTkFrame(self, fg_color="transparent")
        self.file_header.pack(fill="x", padx=12, pady=(0, 2))

        self.file_title = ctk.CTkLabel(
            self.file_header,
            text="Current File: Ready",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        )
        self.file_title.pack(side="left")

        self.speed_lbl = ctk.CTkLabel(
            self.file_header,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#34d399",
        )
        self.speed_lbl.pack(side="right")

        self.file_bar = ctk.CTkProgressBar(
            self,
            orientation="horizontal",
            mode="determinate",
            progress_color="#10b981",
            fg_color="#334155",
            height=6,
        )
        self.file_bar.pack(fill="x", padx=12, pady=(2, 10))
        self.file_bar.set(0)

    def update_progress(
        self,
        overall_frac: float,
        overall_text: str,
        file_frac: float,
        file_text: str,
        speed_text: str = "",
    ):
        self.overall_bar.set(max(0.0, min(1.0, overall_frac)))
        self.overall_title.configure(text=overall_text)
        self.overall_percent_lbl.configure(text=f"{int(overall_frac * 100)}%")

        self.file_bar.set(max(0.0, min(1.0, file_frac)))
        self.file_title.configure(text=file_text)
        self.speed_lbl.configure(text=speed_text)

    def reset(self):
        self.overall_bar.set(0)
        self.file_bar.set(0)
        self.overall_title.configure(text="Overall Progress: 0 / 0 files")
        self.overall_percent_lbl.configure(text="0%")
        self.file_title.configure(text="Current File: Ready")
        self.speed_lbl.configure(text="")


class LogViewer(ctk.CTkFrame):
    """Terminal-like live logging textbox with timestamp, clear and copy actions."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#0f172a", corner_radius=10, **kwargs)

        # Header bar
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(6, 4))

        title = ctk.CTkLabel(
            header,
            text="Activity Logs",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#94a3b8",
        )
        title.pack(side="left")

        clear_btn = ctk.CTkButton(
            header,
            text="Clear Logs",
            width=70,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self.clear,
        )
        clear_btn.pack(side="right", padx=(4, 0))

        # Text box
        self.textbox = ctk.CTkTextbox(
            self,
            wrap="word",
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#020617",
            text_color="#e2e8f0",
            height=120,
        )
        self.textbox.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.textbox.configure(state="disabled")

    def log(self, message: str):
        """Appends timestamped message to the log box."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        
        self.textbox.configure(state="normal")
        self.textbox.insert("end", formatted)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
