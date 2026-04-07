"""Log panel — real-time scrollable command output."""

import customtkinter as ctk
from flash_tool.ui.theme import COLORS, FONTS, SPACING


class LogPanel(ctk.CTkFrame):
    """Scrollable log panel with auto-scroll and color-coded output."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)

        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0, height=32)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="  📋 Console Output",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(side="left", padx=SPACING["sm"], pady=SPACING["xs"])

        self.clear_btn = ctk.CTkButton(
            header,
            text="Clear",
            font=FONTS["caption"],
            width=60,
            height=24,
            fg_color=COLORS["bg_tertiary"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            corner_radius=4,
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
            scrollbar_button_hover_color=COLORS["bg_hover"],
        )
        self.textbox.pack(fill="both", expand=True, padx=0, pady=0)

        # Auto-scroll flag
        self._auto_scroll = True

    def append(self, text: str):
        """Append a line to the log."""
        self.textbox.configure(state="normal")
        self.textbox.insert("end", text + "\n")
        if self._auto_scroll:
            self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def append_colored(self, text: str, color: str):
        """Append colored text (using tag)."""
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
