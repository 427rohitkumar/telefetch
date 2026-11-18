"""
Async Telethon backend wrapper running on a dedicated worker thread.
Handles authentication, channel resolution, message search, and metadata extraction.
"""

import asyncio
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from telethon import TelegramClient, errors, functions, types
from telethon.tl.types import DocumentAttributeFilename, InputMessagesFilterDocument

from src.config import ConfigManager
from src.models import AuthState, ChannelInfo, TelegramFileInfo
from src.utils import matches_pattern, parse_channel_input, sanitize_filename


class TelegramBackend:
    """
    Manages the Telethon client lifecycle on a background asyncio thread.
    Thread-safe and keeps GUI responsive.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.client: Optional[TelegramClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._is_ready = threading.Event()
        self._phone_code_hash: Optional[str] = None
        self._phone_number: Optional[str] = None
        self.auth_state = AuthState.DISCONNECTED
        self._current_user = None

        self._start_event_loop()

    def _start_event_loop(self):
        """Starts dedicated daemon thread with its own asyncio event loop."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._is_ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=run_loop, name="TeleFetch-AsyncLoop", daemon=True)
        self._thread.start()
        self._is_ready.wait()

    def run_coro(self, coro):
        """Runs a coroutine safely on the worker thread's event loop and returns a concurrent.futures.Future."""
        if not self._loop or not self._loop.is_running():
            raise RuntimeError("Async event loop is not running")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    # -------------------------------------------------------------
    # Authentication & Client Lifecycle
    # -------------------------------------------------------------

    def is_connected(self) -> bool:
        """Returns True if client exists and is connected."""
        if not self.client:
            return False
        fut = self.run_coro(self._check_connected_async())
        return fut.result(timeout=5)

    async def _check_connected_async(self) -> bool:
        try:
            return self.client is not None and self.client.is_connected() and await self.client.is_user_authorized()
        except Exception:
            return False

    def init_client(self, api_id: str, api_hash: str) -> None:
        """Initializes or reinitializes the Telethon client instance."""
        fut = self.run_coro(self._init_client_async(api_id, api_hash))
        fut.result(timeout=10)

    async def _init_client_async(self, api_id: str, api_hash: str) -> None:
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass

        session_path = str(self.config_manager.session_path)
        int_api_id = int(api_id) if str(api_id).strip().isdigit() else 0
        
        self.client = TelegramClient(
            session_path,
            api_id=int_api_id,
            api_hash=api_hash.strip(),
            connection_retries=5,
            retry_delay=2,
            auto_reconnect=True,
        )

    def check_saved_session(self) -> Tuple[bool, Optional[str]]:
        """
        Attempts to connect using saved session credentials.
        Returns (is_authorized, user_display_name).
        """
        fut = self.run_coro(self._check_saved_session_async())
        return fut.result(timeout=15)

    async def _check_saved_session_async(self) -> Tuple[bool, Optional[str]]:
        cfg = self.config_manager.config
        if not cfg.api_id or not cfg.api_hash:
            self.auth_state = AuthState.DISCONNECTED
            return False, None

        await self._init_client_async(cfg.api_id, cfg.api_hash)
        
        try:
            await self.client.connect()
            if await self.client.is_user_authorized():
                self._current_user = await self.client.get_me()
                self.auth_state = AuthState.AUTHORIZED
                name = self._current_user.first_name or self._current_user.username or "Telegram User"
                return True, name
            else:
                self.auth_state = AuthState.DISCONNECTED
                return False, None
        except Exception as e:
            self.auth_state = AuthState.ERROR
            return False, str(e)

    def request_otp(self, api_id: str, api_hash: str, phone: str) -> Tuple[bool, str]:
        """
        Connects and requests OTP code sent to Telegram / SMS.
        Returns (success, message).
        """
        fut = self.run_coro(self._request_otp_async(api_id, api_hash, phone))
        return fut.result(timeout=30)

    async def _request_otp_async(self, api_id: str, api_hash: str, phone: str) -> Tuple[bool, str]:
        try:
            await self._init_client_async(api_id, api_hash)
            await self.client.connect()
            
            clean_phone = phone.strip().replace(" ", "").replace("-", "")
            self._phone_number = clean_phone
            
            # Send code request
            sent_code = await self.client.send_code_request(clean_phone)
            self._phone_code_hash = sent_code.phone_code_hash
            self.auth_state = AuthState.CODE_REQUIRED
            return True, "Verification code sent to your Telegram app / SMS."
        except errors.FloodWaitError as e:
            self.auth_state = AuthState.ERROR
            return False, f"Telegram rate limit: Please wait {e.seconds} seconds."
        except errors.PhoneNumberInvalidError:
            self.auth_state = AuthState.ERROR
            return False, "The phone number format is invalid. Include country code (e.g., +91...)."
        except Exception as e:
            self.auth_state = AuthState.ERROR
            return False, f"Failed to send code: {str(e)}"

    def verify_code(self, code: str) -> Tuple[bool, str, bool]:
        """
        Verifies the received OTP code.
        Returns (success, message, requires_2fa_password).
        """
        fut = self.run_coro(self._verify_code_async(code))
        return fut.result(timeout=30)

    async def _verify_code_async(self, code: str) -> Tuple[bool, str, bool]:
        try:
            clean_code = code.strip().replace(" ", "")
            await self.client.sign_in(
                phone=self._phone_number,
                code=clean_code,
                phone_code_hash=self._phone_code_hash,
            )
            self._current_user = await self.client.get_me()
            self.auth_state = AuthState.AUTHORIZED
            name = self._current_user.first_name or self._current_user.username or "User"
            return True, f"Successfully logged in as {name}!", False
        except errors.SessionPasswordNeededError:
            self.auth_state = AuthState.PASSWORD_REQUIRED
            return False, "Two-factor authentication (2FA) is enabled on this account.", True
        except errors.PhoneCodeInvalidError:
            return False, "The verification code entered is invalid.", False
        except errors.PhoneCodeExpiredError:
            return False, "The verification code has expired. Please request a new code.", False
        except Exception as e:
            return False, f"Sign-in error: {str(e)}", False

    def verify_2fa_password(self, password: str) -> Tuple[bool, str]:
        """
        Authenticates with 2FA password.
        Returns (success, message).
        """
        fut = self.run_coro(self._verify_2fa_password_async(password))
        return fut.result(timeout=30)

    async def _verify_2fa_password_async(self, password: str) -> Tuple[bool, str]:
        try:
            await self.client.sign_in(password=password)
            self._current_user = await self.client.get_me()
            self.auth_state = AuthState.AUTHORIZED
            name = self._current_user.first_name or self._current_user.username or "User"
            return True, f"Successfully logged in as {name}!"
        except errors.PasswordHashInvalidError:
            return False, "Incorrect 2FA password."
        except Exception as e:
            return False, f"2FA verification failed: {str(e)}"

    def log_out(self) -> Tuple[bool, str]:
        """Logs out from Telegram session and clears local credentials."""
        fut = self.run_coro(self._log_out_async())
        return fut.result(timeout=10)

    async def _log_out_async(self) -> Tuple[bool, str]:
        try:
            if self.client and await self.client.is_user_authorized():
                await self.client.log_out()
        except Exception:
            pass
        self.auth_state = AuthState.DISCONNECTED
        self._current_user = None
        self.config_manager.clear_credentials()
        return True, "Successfully logged out."

    # -------------------------------------------------------------
    # Channel Verification & Resolution
    # -------------------------------------------------------------

    def resolve_channel(self, channel_input: str) -> Tuple[bool, Optional[ChannelInfo], str]:
        """
        Resolves channel username, invite link, or ID and checks accessibility.
        Returns (success, ChannelInfo, status_message).
        """
        fut = self.run_coro(self._resolve_channel_async(channel_input))
        return fut.result(timeout=20)

    async def _resolve_channel_async(self, channel_input: str) -> Tuple[bool, Optional[ChannelInfo], str]:
        if not self.client or not await self.client.is_user_authorized():
            return False, None, "Please log in to Telegram first."

        cleaned, is_invite = parse_channel_input(channel_input)
        if not cleaned:
            return False, None, "Please enter a valid channel username, invite link, or ID."

        try:
            if is_invite:
                # Handle invite hash
                try:
                    invite_res = await self.client(functions.messages.CheckChatInviteRequest(hash=cleaned))
                    if isinstance(invite_res, types.ChatInviteAlready):
                        chat = invite_res.chat
                        info = ChannelInfo(
                            id=chat.id,
                            title=getattr(chat, "title", "Channel"),
                            username=getattr(chat, "username", None),
                            is_channel=isinstance(chat, types.Channel),
                            participants_count=getattr(chat, "participants_count", None),
                            entity_input=channel_input,
                        )
                        return True, info, f"Channel verified: '{info.title}' (Already Joined)"
                    elif isinstance(invite_res, types.ChatInvite):
                        info = ChannelInfo(
                            id=0,
                            title=invite_res.title,
                            username=None,
                            is_channel=invite_res.channel,
                            participants_count=invite_res.participants_count,
                            entity_input=channel_input,
                        )
                        return True, info, f"Channel verified via invite: '{info.title}' ({invite_res.participants_count or 0} members)"
                except Exception as invite_err:
                    # Fallback to direct resolution
                    pass

            # Resolve entity directly
            target = int(cleaned) if (cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit())) else cleaned
            entity = await self.client.get_entity(target)
            
            title = getattr(entity, "title", getattr(entity, "first_name", str(entity.id)))
            username = getattr(entity, "username", None)
            participants = getattr(entity, "participants_count", None)

            info = ChannelInfo(
                id=entity.id,
                title=title,
                username=username,
                is_channel=isinstance(entity, types.Channel),
                participants_count=participants,
                entity_input=channel_input,
            )
            return True, info, f"Verified: '{title}'"
            
        except errors.UsernameNotOccupiedError:
            return False, None, "Channel username does not exist."
        except errors.UsernameInvalidError:
            return False, None, "Invalid channel username format."
        except errors.ChannelPrivateError:
            return False, None, "This channel is private and your account does not have access."
        except Exception as e:
            return False, None, f"Could not access channel: {str(e)}"

    # -------------------------------------------------------------
    # Message Scanning & File Fetching
    # -------------------------------------------------------------

    def fetch_files_stream(
        self,
        channel_input: str,
        file_extension: str = ".pdf",
        pattern: str = "",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 1000,
        batch_callback: Optional[Callable[[List[TelegramFileInfo], int, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ):
        """
        Asynchronously scans channel messages and streams discovered matching files back via callback.
        """
        fut = self.run_coro(
            self._fetch_files_async(
                channel_input=channel_input,
                file_extension=file_extension,
                pattern=pattern,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                batch_callback=batch_callback,
                log_callback=log_callback,
                cancel_event=cancel_event,
            )
        )
        return fut

    async def _fetch_files_async(
        self,
        channel_input: str,
        file_extension: str,
        pattern: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int,
        batch_callback: Optional[Callable[[List[TelegramFileInfo], int, int], None]],
        log_callback: Optional[Callable[[str], None]],
        cancel_event: Optional[threading.Event],
    ) -> List[TelegramFileInfo]:
        matched_files: List[TelegramFileInfo] = []
        scanned_count = 0
        
        def log(msg: str):
            if log_callback:
                log_callback(msg)

        log(f"Starting scan on '{channel_input}' (Extension: {file_extension}, Pattern: '{pattern or '*'}')...")

        cleaned, is_invite = parse_channel_input(channel_input)
        target = int(cleaned) if (cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit())) else cleaned

        try:
            entity = await self.client.get_entity(target)
            channel_title = getattr(entity, "title", "Channel")
        except Exception as e:
            log(f"Error accessing channel: {e}")
            raise e

        # Normalize extension
        ext_filter = file_extension.lower().strip()
        if ext_filter == "all" or ext_filter == "*.*" or not ext_filter:
            ext_filter = None
        elif not ext_filter.startswith("."):
            ext_filter = f".{ext_filter}"

        batch_buffer: List[TelegramFileInfo] = []
        BATCH_SIZE = 25  # Stream in fast responsive chunks

        scan_limit = limit if limit > 0 else None

        try:
            async for msg in self.client.iter_messages(entity, limit=scan_limit):
                if cancel_event and cancel_event.is_set():
                    log("Scan cancelled by user.")
                    break

                scanned_count += 1
                
                # Check document / file
                if not msg.file or not msg.document:
                    continue

                # Determine filename
                file_name = msg.file.name
                if not file_name:
                    # Look inside document attributes
                    for attr in msg.document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            file_name = attr.file_name
                            break
                if not file_name:
                    ext = msg.file.ext or ".bin"
                    file_name = f"doc_{msg.id}{ext}"

                # Check extension
                base, file_ext = os.path.splitext(file_name)
                file_ext = file_ext.lower()
                if ext_filter and file_ext != ext_filter:
                    continue

                # Check pattern / regex
                if pattern and not matches_pattern(file_name, pattern):
                    continue

                # Check date range
                if msg.date:
                    msg_dt = msg.date
                    if date_from:
                        dt_from_aware = date_from.replace(tzinfo=timezone.utc) if date_from.tzinfo is None else date_from
                        if msg_dt < dt_from_aware:
                            continue
                    if date_to:
                        dt_to_aware = date_to.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc) if date_to.tzinfo is None else date_to
                        if msg_dt > dt_to_aware:
                            continue

                file_info = TelegramFileInfo(
                    message_id=msg.id,
                    file_name=file_name,
                    file_size=msg.file.size or msg.document.size or 0,
                    date=msg.date,
                    mime_type=msg.file.mime_type or "",
                    extension=file_ext,
                    selected=True,
                    channel_id=entity.id,
                    channel_title=channel_title,
                )

                batch_buffer.append(file_info)
                matched_files.append(file_info)

                if len(batch_buffer) >= BATCH_SIZE:
                    if batch_callback:
                        batch_callback(list(batch_buffer), scanned_count, len(matched_files))
                    batch_buffer.clear()

            # Flush remaining batch
            if batch_buffer and batch_callback:
                batch_callback(list(batch_buffer), scanned_count, len(matched_files))
                batch_buffer.clear()

            log(f"Scan completed: Scanned {scanned_count} messages, found {len(matched_files)} matching files.")
            return matched_files

        except Exception as e:
            log(f"Error during scan: {str(e)}")
            raise e
