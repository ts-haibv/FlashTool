"""Log panel — real-time scrollable command output."""

import customtkinter as ctk
from flash_tool.log_utils import strip_ansi
from flash_tool.ui.theme import COLORS, FONTS, RADIUS, SPACING


class LogPanel(ctk.CTkFrame):
    """Scrollable log panel with auto-scroll and color-coded output."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_primary"],
            border_width=1,
            border_color=COLORS["border_subtle"],
            corner_radius=RADIUS["md"],
            **kwargs,
        )

        # Header
        header = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_secondary"],
            corner_radius=RADIUS["md"],
            height=36,
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Console output",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(side="left", padx=SPACING["sm"], pady=SPACING["xs"])

        self.clear_btn = ctk.CTkButton(
            header,
            text="Clear log",
            font=FONTS["caption"],
            width=72,
            height=24,
            fg_color=COLORS["bg_tertiary"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            corner_radius=RADIUS["sm"],
            command=self.clear,
        )
        self.clear_btn.pack(side="right", padx=SPACING["sm"], pady=SPACING["xs"])

        # Text area
        self.textbox = ctk.CTkTextbox(
            self,
            font=FONTS["mono_sm"],
            fg_color=COLORS["bg_primary"],
            text_color=COLORS["text_primary"],
            corner_radius=0,
            wrap="word",
            state="disabled",
            activate_scrollbars=True,
            scrollbar_button_color=COLORS["scrollbar_fg"],
            scrollbar_button_hover_color=COLORS["scrollbar_hover"],
        )
        self.textbox.pack(fill="both", expand=True, padx=0, pady=0)

        # Auto-scroll flag
        self._auto_scroll = True

    def append(self, text: str):
        """Append a line to the log."""
        text = strip_ansi(text)
        self.textbox.configure(state="normal")
        self.textbox.insert("end", text + "\n")
        if self._auto_scroll:
            self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def append_colored(self, text: str, color: str):
        """Append colored text (using tag)."""
        text = strip_ansi(text)
        tag = f"color_{color}"
        self.textbox.configure(state="normal")
        # Tags in CTkTextbox are limited, so we'll just append normally
        self.textbox.insert("end", text + "\n")
        if self._auto_scroll:
            self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear(self):
        """Clear all log content."""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
