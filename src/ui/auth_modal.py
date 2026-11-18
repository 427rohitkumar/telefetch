"""
Authentication modal for Telegram credentials, OTP verification, and 2FA password entry.
"""

import threading
import webbrowser
from typing import Callable, Optional
import customtkinter as ctk

from src.config import AppConfig, ConfigManager
from src.telegram_client import TelegramBackend


class AuthModal(ctk.CTkToplevel):
    """
    Modal dialog for logging into Telegram and managing API credentials.
    """

    def __init__(
        self,
        parent,
        backend: TelegramBackend,
        config_manager: ConfigManager,
        on_login_success: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.backend = backend
        self.config_manager = config_manager
        self.on_login_success = on_login_success

        self.title("Telegram Authentication")
        self.geometry("520x620")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._load_existing_config()

    def _build_ui(self):
        # Container frame
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=20)

        # Title and Instructions
        title_label = ctk.CTkLabel(
            container,
            text="Telegram Authentication",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#f8fafc",
        )
        title_label.pack(anchor="w", pady=(0, 4))

        subtitle = ctk.CTkLabel(
            container,
            text="Connect your Telegram account using Telegram API credentials.",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8",
        )
        subtitle.pack(anchor="w", pady=(0, 14))

        # Help Link
        help_btn = ctk.CTkButton(
            container,
            text="🔗 How to get API ID and Hash (my.telegram.org)",
            fg_color="transparent",
            text_color="#38bdf8",
            hover_color="#1e293b",
            anchor="w",
            font=ctk.CTkFont(size=12, underline=True),
            command=lambda: webbrowser.open("https://my.telegram.org"),
            height=24,
        )
        help_btn.pack(anchor="w", pady=(0, 16))

        # API Credentials Section
        ctk.CTkLabel(
            container,
            text="API ID:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#cbd5e1",
        ).pack(anchor="w")
        self.api_id_entry = ctk.CTkEntry(
            container,
            placeholder_text="e.g. 12345678",
            height=36,
        )
        self.api_id_entry.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(
            container,
            text="API HASH:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#cbd5e1",
        ).pack(anchor="w")
        self.api_hash_entry = ctk.CTkEntry(
            container,
            placeholder_text="e.g. 0123456789abcdef0123456789abcdef",
            height=36,
        )
        self.api_hash_entry.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(
            container,
            text="Phone Number (with Country Code):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#cbd5e1",
        ).pack(anchor="w")
        self.phone_entry = ctk.CTkEntry(
            container,
            placeholder_text="e.g. +919876543210",
            height=36,
        )
        self.phone_entry.pack(fill="x", pady=(2, 10))

        self.remember_var = ctk.BooleanVar(value=True)
        self.remember_cb = ctk.CTkCheckBox(
            container,
            text="Save credentials locally (auto-login on next launch)",
            variable=self.remember_var,
            font=ctk.CTkFont(size=12),
        )
        self.remember_cb.pack(anchor="w", pady=(4, 12))

        # Send Code Button
        self.send_code_btn = ctk.CTkButton(
            container,
            text="Send Verification Code (OTP)",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._on_send_code,
        )
        self.send_code_btn.pack(fill="x", pady=(0, 12))

        # OTP & 2FA Section (Hidden or disabled initially)
        self.otp_frame = ctk.CTkFrame(container, fg_color="#1e293b", corner_radius=8)
        
        self.otp_label = ctk.CTkLabel(
            self.otp_frame,
            text="Enter Verification Code (OTP):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#cbd5e1",
        )
        self.otp_label.pack(anchor="w", padx=14, pady=(10, 2))

        self.otp_entry = ctk.CTkEntry(
            self.otp_frame,
            placeholder_text="Code sent to Telegram app / SMS",
            height=36,
        )
        self.otp_entry.pack(fill="x", padx=14, pady=(0, 10))

        self.verify_code_btn = ctk.CTkButton(
            self.otp_frame,
            text="Verify OTP & Login",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=36,
            fg_color="#10b981",
            hover_color="#059669",
            command=self._on_verify_code,
        )
        self.verify_code_btn.pack(fill="x", padx=14, pady=(0, 10))

        # 2FA Frame
        self.twofa_frame = ctk.CTkFrame(container, fg_color="#1e293b", corner_radius=8)
        
        self.twofa_label = ctk.CTkLabel(
            self.twofa_frame,
            text="Two-Factor (2FA) Password:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#cbd5e1",
        )
        self.twofa_label.pack(anchor="w", padx=14, pady=(10, 2))

        self.twofa_entry = ctk.CTkEntry(
            self.twofa_frame,
            show="*",
            placeholder_text="Enter your Cloud Password",
            height=36,
        )
        self.twofa_entry.pack(fill="x", padx=14, pady=(0, 10))

        self.verify_twofa_btn = ctk.CTkButton(
            self.twofa_frame,
            text="Confirm 2FA Password",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=36,
            fg_color="#10b981",
            hover_color="#059669",
            command=self._on_verify_twofa,
        )
        self.verify_twofa_btn.pack(fill="x", padx=14, pady=(0, 10))

        # Status / Error Alert label
        self.status_lbl = ctk.CTkLabel(
            container,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#38bdf8",
            wraplength=460,
        )
        self.status_lbl.pack(fill="x", pady=(10, 0))

    def _load_existing_config(self):
        cfg = self.config_manager.config
        if cfg.api_id:
            self.api_id_entry.insert(0, str(cfg.api_id))
        if cfg.api_hash:
            self.api_hash_entry.insert(0, cfg.api_hash)
        if cfg.phone:
            self.phone_entry.insert(0, cfg.phone)
        self.remember_var.set(cfg.remember_credentials)

    def _set_status(self, text: str, is_error: bool = False, is_success: bool = False):
        if is_error:
            self.status_lbl.configure(text=text, text_color="#f87171")
        elif is_success:
            self.status_lbl.configure(text=text, text_color="#34d399")
        else:
            self.status_lbl.configure(text=text, text_color="#38bdf8")

    def _on_send_code(self):
        api_id = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()
        phone = self.phone_entry.get().strip()

        if not api_id or not api_id.isdigit():
            self._set_status("Please enter a valid numeric API ID.", is_error=True)
            return
        if not api_hash or len(api_hash) < 10:
            self._set_status("Please enter a valid API HASH.", is_error=True)
            return
        if not phone or len(phone) < 7:
            self._set_status("Please enter a valid phone number with country code (e.g. +91...).", is_error=True)
            return

        self._set_status("Connecting to Telegram and sending verification code...")
        self.send_code_btn.configure(state="disabled")

        def worker():
            success, msg = self.backend.request_otp(api_id, api_hash, phone)
            
            def on_ui():
                self.send_code_btn.configure(state="normal")
                if success:
                    self._set_status(msg, is_success=True)
                    # Save creds if remember checked
                    cfg = self.config_manager.config
                    cfg.api_id = api_id
                    cfg.api_hash = api_hash
                    cfg.phone = phone
                    cfg.remember_credentials = self.remember_var.get()
                    self.config_manager.save(cfg)

                    # Show OTP frame
                    self.otp_frame.pack(fill="x", pady=(10, 0))
                    self.otp_entry.focus()
                else:
                    self._set_status(msg, is_error=True)

            self.after(0, on_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _on_verify_code(self):
        code = self.otp_entry.get().strip()
        if not code:
            self._set_status("Please enter the verification code received.", is_error=True)
            return

        self._set_status("Verifying code...")
        self.verify_code_btn.configure(state="disabled")

        def worker():
            success, msg, needs_2fa = self.backend.verify_code(code)

            def on_ui():
                self.verify_code_btn.configure(state="normal")
                if success:
                    self._set_status(msg, is_success=True)
                    if self.on_login_success:
                        self.on_login_success(msg)
                    self.after(1200, self.destroy)
                elif needs_2fa:
                    self._set_status("2FA is enabled. Enter your password below.", is_error=False)
                    self.twofa_frame.pack(fill="x", pady=(10, 0))
                    self.twofa_entry.focus()
                else:
                    self._set_status(msg, is_error=True)

            self.after(0, on_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _on_verify_twofa(self):
        pwd = self.twofa_entry.get()
        if not pwd:
            self._set_status("Please enter your 2FA password.", is_error=True)
            return

        self._set_status("Verifying 2FA password...")
        self.verify_twofa_btn.configure(state="disabled")

        def worker():
            success, msg = self.backend.verify_2fa_password(pwd)

            def on_ui():
                self.verify_twofa_btn.configure(state="normal")
                if success:
                    self._set_status(msg, is_success=True)
                    if self.on_login_success:
                        self.on_login_success(msg)
                    self.after(1200, self.destroy)
                else:
                    self._set_status(msg, is_error=True)

            self.after(0, on_ui)

        threading.Thread(target=worker, daemon=True).start()
