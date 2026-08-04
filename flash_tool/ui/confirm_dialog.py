"""Custom confirmation dialog matching the app theme."""

import customtkinter as ctk
from flash_tool.ui.theme import COLORS, FONTS, RADIUS, SPACING


class ConfirmDialog(ctk.CTkToplevel):
    """Modern theme-consistent confirmation dialog."""

    def __init__(self, parent, title: str, message: str):
        super().__init__(parent)
        self.title(title)
        self.result = False

        # Apply theme colors
        self.configure(fg_color=COLORS["bg_primary"])

        # Geometry
        width = 480
        height = 320

        # Center relative to parent window
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()

        # Fallback to screen center if parent window is not ready/mapped
        if parent_w <= 1 or parent_h <= 1:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - width) // 2
            y = (screen_h - height) // 2
        else:
            x = parent_x + (parent_w - width) // 2
            y = parent_y + (parent_h - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)

        # Make transient to parent
        self.transient(parent)

        # Ensure window is on top
        self.lift()
        self.attributes("-topmost", True)

        # Layout using simple packs (order of packing determines spatial layout)
        # 1. Title/Header label (packed at top)
        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=FONTS["heading_md"],
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.title_label.pack(fill="x", padx=24, pady=(24, 12), side="top")

        # 2. Buttons frame (packed at bottom first so it is guaranteed visibility)
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", side="bottom", padx=24, pady=24)

        # Action Buttons inside buttons frame
        self.yes_btn = ctk.CTkButton(
            self.btn_frame,
            text="Yes",
            font=FONTS["heading_sm"],
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["on_accent"],
            width=100,
            height=36,
            corner_radius=RADIUS["sm"],
            command=self.on_yes,
        )
        self.yes_btn.pack(side="right", padx=(12, 0))

        self.no_btn = ctk.CTkButton(
            self.btn_frame,
            text="No",
            font=FONTS["heading_sm"],
            fg_color=COLORS["bg_tertiary"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            width=100,
            height=36,
            corner_radius=RADIUS["sm"],
            command=self.on_no,
        )
        self.no_btn.pack(side="right")

        # 3. Message textbox (packed in the middle, scrollable, borderless to look like a label)
        self.msg_box = ctk.CTkTextbox(
            self,
            font=FONTS["body"],
            fg_color=COLORS["bg_primary"],
            text_color=COLORS["text_secondary"],
            wrap="word",
            activate_scrollbars=True,
            scrollbar_button_color=COLORS["scrollbar_fg"],
            scrollbar_button_hover_color=COLORS["scrollbar_hover"],
            border_width=0,
        )
        self.msg_box.pack(fill="both", expand=True, padx=24, pady=12)
        self.msg_box.insert("1.0", message)
        self.msg_box.configure(state="disabled")

        # Focus and keyboard bindings
        self.yes_btn.focus_set()
        self.bind("<Return>", lambda e: self.on_yes())
        self.bind("<Escape>", lambda e: self.on_no())
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        # Force map window and position it correctly before grabbing focus
        self.update()
        self.grab_set()

    def on_yes(self):
        self.result = True
        self.destroy()

    def on_no(self):
        self.result = False
        self.destroy()

    def on_cancel(self):
        self.result = False
        self.destroy()


def ask_yes_no(parent, title: str, message: str) -> bool:
    """Helper function to show ConfirmDialog and return result."""
    dialog = ConfirmDialog(parent, title, message)
    dialog.wait_window()
    return dialog.result
