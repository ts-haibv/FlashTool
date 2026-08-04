"""Update dialog widget."""

import os
import sys
import threading
import tempfile
import webbrowser
import customtkinter as ctk
from tkinter import messagebox

from flash_tool.ui.theme import COLORS, FONTS, RADIUS, SPACING
from flash_tool.updater import (
    check_for_updates,
    download_file_with_progress,
    apply_update,
    restart_application,
)


class UpdateDialog(ctk.CTkToplevel):
    """Modern software update dialog matching the app theme."""

    def __init__(
        self,
        parent,
        current_version: str,
        update_info: dict | None = None,
        error_msg: str | None = None,
    ):
        super().__init__(parent)
        self.title("Software Update")
        self.current_version = current_version
        self.update_info = update_info
        self.error_msg = error_msg

        # Apply theme colors
        self.configure(fg_color=COLORS["bg_primary"])

        # Geometry
        self.width = 540
        self.height = 420

        # Center relative to parent window
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()

        if parent_w <= 1 or parent_h <= 1:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - self.width) // 2
            y = (screen_h - self.height) // 2
        else:
            x = parent_x + (parent_w - self.width) // 2
            y = parent_y + (parent_h - self.height) // 2

        self.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.resizable(False, False)

        # Make transient
        self.transient(parent)
        self.lift()
        self.attributes("-topmost", True)

        # Internal state
        self.stopped = False
        self.temp_file_path = None
        self.download_thread = None

        # Build structural container
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=24, pady=24)

        # Bind window close event
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initialize dialog state
        if self.error_msg:
            self._switch_state("error")
        elif self.update_info is None:
            self._switch_state("checking")
            self._start_check()
        else:
            if self.update_info.get("update_available"):
                self._switch_state("update_available")
            else:
                self._switch_state("up_to_date")

        self.update()
        self.grab_set()

    def _switch_state(self, state: str):
        """Rebuild the UI matching the requested state."""
        # Clear container
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if state == "checking":
            self._build_checking_ui()
        elif state == "up_to_date":
            self._build_up_to_date_ui()
        elif state == "update_available":
            self._build_update_available_ui()
        elif state == "downloading":
            self._build_downloading_ui()
        elif state == "success":
            self._build_success_ui()
        elif state == "error":
            self._build_error_ui()

    # ── Checking State UI ───────────────────────────────────────────────────
    def _build_checking_ui(self):
        title = ctk.CTkLabel(
            self.content_frame,
            text="Checking for updates",
            font=FONTS["heading_lg"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        title.pack(fill="x", pady=(10, 20))

        # Text status
        self.check_status_label = ctk.CTkLabel(
            self.content_frame,
            text="Contacting update server...",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        )
        self.check_status_label.pack(pady=(40, 10))

        # Indeterminate progress bar
        self.checking_progress = ctk.CTkProgressBar(
            self.content_frame,
            fg_color=COLORS["bg_secondary"],
            progress_color=COLORS["accent_blue"],
            height=6,
            mode="indeterminate",
        )
        self.checking_progress.pack(fill="x", padx=40, pady=(10, 40))
        self.checking_progress.start()

        # Bottom buttons
        btn_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            font=FONTS["heading_sm"],
            fg_color=COLORS["bg_tertiary"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            width=100,
            height=36,
            corner_radius=RADIUS["sm"],
            command=self.on_close,
        )
        cancel_btn.pack(side="right")

    def _start_check(self):
        """Launch update check in a background thread."""
        def run():
            info = check_for_updates(self.current_version)
            if info and info.get("update_available"):
                self.after(0, self._on_check_success, info)
            elif info is not None:
                self.after(0, self._switch_state, "up_to_date")
            else:
                self.after(0, self._on_check_failed, "Failed to query release updates. Please check your internet connection.")

        threading.Thread(target=run, daemon=True).start()

    def _on_check_success(self, info: dict):
        self.update_info = info
        self._switch_state("update_available")

    def _on_check_failed(self, error_msg: str):
        self.error_msg = error_msg
        self._switch_state("error")

    # ── Up to Date State UI ──────────────────────────────────────────────────
    def _build_up_to_date_ui(self):
        title = ctk.CTkLabel(
            self.content_frame,
            text="You're up to date",
            font=FONTS["heading_lg"],
            text_color=COLORS["accent_green"],
            anchor="w",
        )
        title.pack(fill="x", pady=(10, 10))

        btn_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        close_btn = ctk.CTkButton(
            btn_frame,
            text="Close",
            font=FONTS["heading_sm"],
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["on_accent"],
            width=100,
            height=36,
            corner_radius=RADIUS["sm"],
            command=self.on_close,
        )
        close_btn.pack(side="right")

        desc = ctk.CTkLabel(
            self.content_frame,
            text=f"FlashTool v{self.current_version} is currently the newest version available.",
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
            justify="center",
            wraplength=480,
        )
        desc.pack(expand=True)

    # ── Update Available State UI ────────────────────────────────────────────
    def _build_update_available_ui(self):
        latest_version = self.update_info.get("latest_version", "unknown")
        size_bytes = self.update_info.get("size", 0)
        size_str = f" • {size_bytes / (1024 * 1024):.1f} MB" if size_bytes > 0 else ""

        title = ctk.CTkLabel(
            self.content_frame,
            text=f"New update available: {latest_version}",
            font=FONTS["heading_lg"],
            text_color=COLORS["accent_green"],
            anchor="w",
        )
        title.pack(fill="x", pady=(10, 5))

        meta = ctk.CTkLabel(
            self.content_frame,
            text=f"Current version: v{self.current_version}{size_str}",
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        meta.pack(fill="x", pady=(0, 15))

        # Bottom Buttons (Packed first at the bottom to guarantee visibility)
        btn_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        # Check if we run from compiled exe
        is_frozen = getattr(sys, "frozen", False)

        if is_frozen:
            update_text = "Update Now"
            update_cmd = self.on_start_download
        else:
            update_text = "Open Releases Page"
            update_cmd = self.on_open_browser

        self.action_btn = ctk.CTkButton(
            btn_frame,
            text=update_text,
            font=FONTS["heading_sm"],
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["on_accent"],
            width=140,
            height=36,
            corner_radius=RADIUS["sm"],
            command=update_cmd,
        )
        self.action_btn.pack(side="right", padx=(12, 0))

        later_btn = ctk.CTkButton(
            btn_frame,
            text="Later",
            font=FONTS["heading_sm"],
            fg_color=COLORS["bg_tertiary"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            width=100,
            height=36,
            corner_radius=RADIUS["sm"],
            command=self.on_close,
        )
        later_btn.pack(side="right")

        # Release Notes Label
        notes_label = ctk.CTkLabel(
            self.content_frame,
            text="Release Notes:",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        notes_label.pack(fill="x", pady=(0, 5))

        # Scrollable Release Notes Textbox (Fills the remaining center space)
        notes_box = ctk.CTkTextbox(
            self.content_frame,
            font=FONTS["body_sm"],
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            wrap="word",
            activate_scrollbars=True,
            scrollbar_button_color=COLORS["scrollbar_fg"],
            scrollbar_button_hover_color=COLORS["scrollbar_hover"],
        )
        notes_box.pack(fill="both", expand=True, pady=(0, 20))
        notes_box.insert("1.0", self.update_info.get("release_notes", ""))
        notes_box.configure(state="disabled")

    # ── Downloading State UI ────────────────────────────────────────────────
    def _build_downloading_ui(self):
        title = ctk.CTkLabel(
            self.content_frame,
            text="Downloading update",
            font=FONTS["heading_lg"],
            text_color=COLORS["accent_blue"],
            anchor="w",
        )
        title.pack(fill="x", pady=(10, 5))

        self.dl_status_label = ctk.CTkLabel(
            self.content_frame,
            text="Connecting to download server...",
            font=FONTS["body_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.dl_status_label.pack(fill="x", pady=(10, 10))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self.content_frame,
            fg_color=COLORS["bg_secondary"],
            progress_color=COLORS["accent_blue"],
            height=12,
        )
        self.progress_bar.pack(fill="x", pady=(5, 5))
        self.progress_bar.set(0.0)

        # Percent and download rate indicators
        self.dl_stats_label = ctk.CTkLabel(
            self.content_frame,
            text="0% (0.0 MB / -- MB)",
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.dl_stats_label.pack(fill="x", pady=(5, 20))

        # Cancel/Stop button
        btn_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            font=FONTS["heading_sm"],
            fg_color=COLORS["bg_tertiary"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            width=100,
            height=36,
            corner_radius=RADIUS["sm"],
            command=self.on_cancel_download,
        )
        cancel_btn.pack(side="right")

    def on_start_download(self):
        """Transition UI and launch download worker thread."""
        download_url = self.update_info.get("download_url")
        if not download_url:
            messagebox.showerror(
                "Error",
                "Direct binary download URL not found for your platform.\n\n"
                "Please download the update manually from GitHub.",
            )
            self.on_open_browser()
            return

        self._switch_state("downloading")
        self.stopped = False
        self.download_thread = threading.Thread(target=self._run_download, daemon=True)
        self.download_thread.start()

    def _run_download(self):
        """Background download operation."""
        temp_dir = tempfile.gettempdir()
        asset_name = self.update_info.get("asset_name") or "FlashTool-update"
        self.temp_file_path = os.path.join(temp_dir, asset_name)

        if os.path.exists(self.temp_file_path):
            try:
                os.remove(self.temp_file_path)
            except Exception:
                pass

        success = download_file_with_progress(
            self.update_info["download_url"],
            self.temp_file_path,
            self._on_download_progress_callback,
            self._check_stopped,
        )

        if not self.stopped:
            if success:
                self.after(0, self._on_download_complete)
            else:
                self.after(0, self._on_download_failed, "Network error or connection timed out.")

    def _check_stopped(self) -> bool:
        return self.stopped

    def _on_download_progress_callback(self, downloaded: int, total: int, elapsed: float):
        """Thread-safe UI update scheduler."""
        self.after(0, self._update_download_progress, downloaded, total, elapsed)

    def _update_download_progress(self, downloaded: int, total: int, elapsed: float):
        """Perform GUI progress calculations and updates (Main thread)."""
        if self.stopped or self.state_check_fails("downloading"):
            return

        pct = downloaded / total if total > 0 else 0.0
        self.progress_bar.set(pct)

        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024) if total > 0 else 0.0
        speed = downloaded / elapsed if elapsed > 0 else 0
        speed_mb = speed / (1024 * 1024)

        pct_int = int(pct * 100)
        self.dl_status_label.configure(text=f"Downloading update files... {pct_int}%")

        if total_mb > 0:
            stats_text = f"{pct_int}% ({downloaded_mb:.1f} MB / {total_mb:.1f} MB) • {speed_mb:.2f} MB/s"
        else:
            stats_text = f"{downloaded_mb:.1f} MB downloaded • {speed_mb:.2f} MB/s"
        self.dl_stats_label.configure(text=stats_text)

    def state_check_fails(self, required_state: str) -> bool:
        """Sanity check to verify window widgets weren't destroyed/changed."""
        try:
            return not hasattr(self, "progress_bar")
        except Exception:
            return True

    def on_cancel_download(self):
        """Stop download thread and exit dialog."""
        self.stopped = True
        self.on_close()

    def _on_download_complete(self):
        """Download phase finished. Switch to installing/applying phase."""
        self.dl_status_label.configure(text="Applying updates...")
        self.progress_bar.set(1.0)
        
        # Apply the update swap
        def run_apply():
            try:
                ok = apply_update(self.temp_file_path)
                if ok:
                    self.after(0, self._switch_state, "success")
                else:
                    self.after(0, self._on_download_failed, "Failed to swap binary files. Permission denied or file locked.")
            except Exception as e:
                self.after(0, self._on_download_failed, str(e))

        threading.Thread(target=run_apply, daemon=True).start()

    def _on_download_failed(self, error_msg: str):
        self.error_msg = error_msg
        self._switch_state("error")

    # ── Success State UI ────────────────────────────────────────────────────
    def _build_success_ui(self):
        title = ctk.CTkLabel(
            self.content_frame,
            text="Update completed",
            font=FONTS["heading_lg"],
            text_color=COLORS["accent_green"],
            anchor="w",
        )
        title.pack(fill="x", pady=(10, 10))

        btn_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        restart_btn = ctk.CTkButton(
            btn_frame,
            text="Restart Now",
            font=FONTS["heading_sm"],
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["success_hover"],
            text_color="#101117",
            width=130,
            height=36,
            corner_radius=RADIUS["sm"],
            command=self.on_restart,
        )
        restart_btn.pack(side="right")

        desc = ctk.CTkLabel(
            self.content_frame,
            text="FlashTool has been updated successfully to the latest version!\n\nPlease restart the application now to run the new version.",
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
            justify="center",
            wraplength=480,
        )
        desc.pack(expand=True)

    def on_restart(self):
        """Exit current app and trigger relaunch."""
        self.destroy()
        restart_application()

    # ── Error State UI ──────────────────────────────────────────────────────
    def _build_error_ui(self):
        title = ctk.CTkLabel(
            self.content_frame,
            text="Update failed",
            font=FONTS["heading_lg"],
            text_color=COLORS["accent_red"],
            anchor="w",
        )
        title.pack(fill="x", pady=(10, 10))

        btn_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        close_btn = ctk.CTkButton(
            btn_frame,
            text="Close",
            font=FONTS["heading_sm"],
            fg_color=COLORS["bg_tertiary"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            width=100,
            height=36,
            corner_radius=RADIUS["sm"],
            command=self.on_close,
        )
        close_btn.pack(side="right")

        if self.update_info and self.update_info.get("html_url"):
            fallback_btn = ctk.CTkButton(
                btn_frame,
                text="Download Manually",
                font=FONTS["heading_sm"],
                fg_color=COLORS["accent_blue"],
                hover_color=COLORS["primary_hover"],
                text_color=COLORS["on_accent"],
                width=160,
                height=36,
                corner_radius=RADIUS["sm"],
                command=self.on_open_browser,
            )
            fallback_btn.pack(side="right", padx=(0, 12))

        desc = ctk.CTkLabel(
            self.content_frame,
            text=getattr(self, "error_msg", "An unexpected error occurred during update."),
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
            justify="center",
            wraplength=480,
        )
        desc.pack(expand=True)

    # ── Shared Actions ──────────────────────────────────────────────────────
    def on_open_browser(self):
        """Open the GitHub Release details in user browser."""
        url = self.update_info.get("html_url") if self.update_info else f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases"
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open browser: {e}")

    def on_close(self):
        self.stopped = True
        self.grab_release()
        self.destroy()
