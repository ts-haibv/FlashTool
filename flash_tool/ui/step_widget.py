"""Step widget — displays a single flash step with progress."""

import customtkinter as ctk
from flash_tool.ui.theme import COLORS, FONTS, SPACING, STATUS_CONFIG


class StepWidget(ctk.CTkFrame):
    """A card representing one flash step with icon, name, progress bar, and status."""

    def __init__(self, master, step_id: int, step_name: str, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_secondary"],
            corner_radius=8,
            height=52,
            **kwargs,
        )
        self.step_id = step_id
        self.pack_propagate(False)

        # ── Layout ──
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        # ID badge
        self.id_label = ctk.CTkLabel(
            self,
            text=f" {step_id:2d} ",
            font=FONTS["body_sm"],
            text_color=COLORS["text_muted"],
            width=36,
        )
        self.id_label.grid(row=0, column=0, padx=(SPACING["sm"], 0), pady=SPACING["sm"])

        # Step name
        self.name_label = ctk.CTkLabel(
            self,
            text=step_name,
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.name_label.grid(row=0, column=1, padx=SPACING["sm"], pady=SPACING["sm"], sticky="w")

        # Status label
        self.status_label = ctk.CTkLabel(
            self,
            text="⏳ Pending",
            font=FONTS["caption"],
            text_color=COLORS["status_pending"],
            width=100,
            anchor="e",
        )
        self.status_label.grid(row=0, column=2, padx=SPACING["sm"], pady=SPACING["sm"], sticky="e")

        # Progress bar (hidden initially)
        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=3,
            fg_color=COLORS["progress_bg"],
            progress_color=COLORS["progress_fill"],
            corner_radius=2,
        )
        self.progress_bar.grid(row=1, column=0, columnspan=3, padx=SPACING["md"], pady=(0, 4), sticky="ew")
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()  # Hidden until running

    def update_status(self, status: str, progress: float = 0.0, message: str = ""):
        """Update the step display."""
        cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["pending"])

        # Update status label
        display_text = f"{cfg['icon']} {message or cfg['label']}"
        self.status_label.configure(text=display_text, text_color=cfg["color"])

        # Show/hide progress bar
        if status in ("running", "waiting"):
            self.progress_bar.grid()
            self.progress_bar.set(max(0.01, progress))
            self.configure(fg_color=COLORS["bg_tertiary"])
            self.progress_bar.configure(
                progress_color=COLORS["accent_orange"] if status == "running" else COLORS["accent_yellow"]
            )
        elif status == "success":
            self.progress_bar.grid()
            self.progress_bar.set(1.0)
            self.progress_bar.configure(progress_color=COLORS["accent_green"])
            self.configure(fg_color=COLORS["bg_secondary"])
        elif status == "failed":
            self.progress_bar.grid()
            self.progress_bar.configure(progress_color=COLORS["accent_red"])
            self.configure(fg_color=COLORS["bg_secondary"])
        else:
            self.progress_bar.grid_remove()
            self.configure(fg_color=COLORS["bg_secondary"])

    def set_active(self, active: bool):
        """Highlight the active step."""
        if active:
            self.configure(
                fg_color=COLORS["bg_tertiary"],
                border_width=1,
                border_color=COLORS["accent_blue"],
            )
        else:
            self.configure(
                fg_color=COLORS["bg_secondary"],
                border_width=0,
            )
