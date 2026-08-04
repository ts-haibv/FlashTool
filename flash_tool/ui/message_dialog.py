"""Theme-consistent informational and error dialogs."""

import customtkinter as ctk

from flash_tool.ui.theme import COLORS, FONTS, RADIUS, SPACING


class MessageDialog(ctk.CTkToplevel):
    """Modal single-action dialog for app feedback."""

    def __init__(self, parent, title: str, message: str, level: str = "error"):
        super().__init__(parent)
        self.title(title)
        self.configure(fg_color=COLORS["bg_primary"])

        accent = COLORS["accent_green"] if level == "info" else COLORS["accent_red"]
        marker = "i" if level == "info" else "!"
        width, height = 520, 320

        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        if parent_w <= 1 or parent_h <= 1:
            x = (self.winfo_screenwidth() - width) // 2
            y = (self.winfo_screenheight() - height) // 2
        else:
            x = parent_x + (parent_w - width) // 2
            y = parent_y + (parent_h - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.close)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["lg"], SPACING["sm"]))

        ctk.CTkLabel(
            header,
            text=marker,
            width=32,
            height=32,
            corner_radius=RADIUS["sm"],
            fg_color=accent,
            text_color=COLORS["on_accent"],
            font=FONTS["heading_sm"],
        ).pack(side="left", padx=(0, SPACING["sm"]))

        ctk.CTkLabel(
            header,
            text=title,
            font=FONTS["heading_md"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        body = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_tertiary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RADIUS["md"],
        )
        body.pack(fill="both", expand=True, padx=SPACING["lg"], pady=SPACING["sm"])

        ctk.CTkLabel(
            body,
            text=message,
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
            anchor="nw",
            justify="left",
            wraplength=460,
        ).pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["md"])

        self.ok_btn = ctk.CTkButton(
            self,
            text="OK",
            font=FONTS["heading_sm"],
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["on_accent"],
            width=100,
            height=36,
            corner_radius=RADIUS["sm"],
            command=self.close,
        )
        self.ok_btn.pack(anchor="e", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["lg"]))

        self.bind("<Return>", lambda _: self.close())
        self.bind("<Escape>", lambda _: self.close())
        self.update()
        self.ok_btn.focus_set()
        self.grab_set()
        self.lift()

    def close(self):
        self.grab_release()
        self.destroy()


def show_error(parent, title: str, message: str) -> None:
    """Show a themed error dialog and wait for it to close."""
    dialog = MessageDialog(parent, title, message, level="error")
    dialog.wait_window()


def show_info(parent, title: str, message: str) -> None:
    """Show a themed informational dialog and wait for it to close."""
    dialog = MessageDialog(parent, title, message, level="info")
    dialog.wait_window()
