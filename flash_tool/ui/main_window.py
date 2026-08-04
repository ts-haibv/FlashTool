"""Main application window — ties all components together."""

import os
import shutil
import subprocess
import sys
import threading
import customtkinter as ctk
from tkinter import filedialog
from tkinter import font as tkfont

from flash_tool.config import (
    APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT,
    PLATFORM_NAME,
    scan_rom_folder,
    get_clean_env,
)
from flash_tool.device_manager import (
    get_adb_bootloader_unlock_status,
    get_bootloader_unlock_status,
    get_device_state,
    parse_bootloader_unlock_status,
    reboot_to_bootloader,
    unlock_bootloader,
)
from flash_tool.flash_worker import FlashWorker, FlashProgress, StepStatus
from flash_tool.profiles.g6_ramba import build_g6_ramba_steps, build_suw_only_steps
from flash_tool.profiles.script_device import build_script_device_steps
from flash_tool.profiles.auto_detect import (
    detect_device,
    detect_variant,
    get_g6_variants,
    resolve_g6_images,
    AUTO_DETECT_LABEL,
    G6_FAMILY_LABEL,
    G6_FAMILY_MODELS,
)
from flash_tool.rom_type import AUTO_ROM_TYPE, OFFICIAL_ROM_TYPE, JENKINS_ROM_TYPE
from flash_tool.ui.theme import COLORS, FONTS, RADIUS, SPACING
from flash_tool.ui.step_widget import StepWidget
from flash_tool.ui.log_panel import LogPanel
from flash_tool.ui.message_dialog import show_error, show_info
from flash_tool.ui.scrolling import WheelScrollManager
from flash_tool.ui import ask_yes_no
from flash_tool.updater import check_for_updates
from flash_tool.ui.update_dialog import UpdateDialog


class CircularSpinner(ctk.CTkCanvas):
    """Indeterminate circular loading spinner."""

    def __init__(self, parent, size=16, color=COLORS["accent_blue"], bg=COLORS["bg_secondary"]):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size
        self.color = color
        self.angle = 0
        self.running = False

    def start(self):
        if not self.running:
            self.running = True
            self._animate()

    def stop(self):
        self.running = False
        self.delete("all")

    def _draw(self):
        self.delete("all")
        # Draw rotating arc segment
        extent = 120
        self.create_arc(
            2, 2, self.size - 2, self.size - 2,
            start=self.angle, extent=extent,
            outline=self.color, width=2, style="arc"
        )

    def _animate(self):
        if not self.running:
            return
        self.angle = (self.angle + 12) % 360
        self._draw()
        self.after(30, self._animate)


class MainWindow(ctk.CTk):
    """Main application window."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ── Window Setup ──
        self.title(f"{APP_NAME} v{APP_VERSION} — ROM Flash Tool")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        # Keep the window usable on smaller laptop displays.  Individual
        # content areas provide their own scrolling when the viewport is
        # shorter than the complete configuration form.
        self.minsize(860, 540)
        self.configure(fg_color=COLORS["bg_primary"])

        # Set window icon
        self._set_icon()

        # State
        self.current_model = ctk.StringVar(value=AUTO_DETECT_LABEL)
        self.SCRIPT_PROFILES = {
            "PS10": {
                "script": "flash_ps10.sh",
                "variant_arg": "-v",
                "variants": ["mn3", "pdn3", "pen3", "phn3", "tan3", "tdn3", "ten3"],
                "variant_dirs": {
                    "mn3": "MN3",
                    "pdn3": "PDN3",
                    "pen3": "PEN3",
                    "phn3": "PHN3",
                    "tan3": "TAN3",
                    "tdn3": "TDN3",
                    "ten3": "TEN3",
                },
                "default_args": ["-w"],
                "default_variant": "mn3",
            },
            "PS11": {
                "script": "flash_ps11.sh",
                "variant_arg": "-v",
                "variants": ["kira", "mn4", "pdn4", "pen4", "phn4", "tan4", "ten4"],
                "variant_dirs": {
                    "kira": "Kira",
                    "mn4": "MN4",
                    "pdn4": "PDN4",
                    "pen4": "PEN4",
                    "phn4": "Kira/PHN4",
                    "tan4": "Kira/TAN4",
                    "ten4": "Kira/TEN4",
                },
                "default_args": ["-w"],
                "default_variant": "kira",
            },
            "E11": {
                "script": "flash_e11.sh",
                "variant_arg": "-m",
                "variants": ["MC6", "PDC6", "PEC6", "PHC6", "PKC6"],
                "variant_dirs": {
                    "MC6": "MC6",
                    "PDC6": "PDC6",
                    "PEC6": "PEC6",
                    "PHC6": "PHC6",
                    "PKC6": "PKC6",
                },
                "default_args": ["--wipe"],
                "default_variant": "MC6",
            },
            "E10": {
                "script": "flash_e10.sh",
                "variant_arg": "-m",
                "variants": ["MC5", "PDC5", "PEC5", "PHC5", "PKC5", "TAC5", "TDC5", "TEC5"],
                "variant_dirs": {
                    "MC5": "MC5",
                    "PDC5": "PDC5",
                    "PEC5": "PEC5",
                    "PHC5": "PHC5",
                    "PKC5": "PKC5",
                    "TAC5": "TAC5",
                    "TDC5": "TDC5",
                    "TEC5": "TEC5",
                },
                "default_args": ["--wipe"],
                "default_variant": "MC5",
            },
            "E9": {
                "script": "flash_e9.sh",
                "variant_arg": "-m",
                "variants": ["MC4", "PDC4", "PEC4", "PHC4", "PKC4", "TAC4", "TDC4", "TEC4"],
                "variant_dirs": {
                    "MC4": "MC4",
                    "PDC4": "PDC4",
                    "PEC4": "PEC4",
                    "PHC4": "PHC4",
                    "PKC4": "PKC4",
                    "TAC4": "TAC4",
                    "TDC4": "TDC4",
                    "TEC4": "TEC4",
                },
                "default_args": ["--wipe"],
                "default_variant": "MC4",
            },
        }
        self.rom_path: str = ""
        self.detected_images: dict[str, list[str]] = {}
        self.selected_images: dict[str, str] = {}
        self.selected_script_variants: dict[str, str] = {
            model: config["default_variant"]
            for model, config in self.SCRIPT_PROFILES.items()
        }
        self.use_super = False
        self.flash_steps = []
        self.worker: FlashWorker | None = None
        self.step_widgets: dict[int, StepWidget] = {}
        self.auto_detected_device: str | None = None
        self.auto_detected_variant: str | None = None
        self.selected_g6_variant: str | None = None
        self.rom_type_var = ctk.StringVar(value=AUTO_ROM_TYPE)
        self.selected_rom_type = ""
        self.device_state = "disconnected"
        self.device_serial: str | None = None
        self.unlock_status: bool | None = None
        self.unlock_status_serial: str | None = None
        self.unlock_status_mode: str | None = None
        self._unlock_status_pending = False
        self._unlock_status_pending_key: tuple[str, str] | None = None

        # Device polling
        self._poll_running = True
        self._poll_after_id = None
        self._device_poll_lock = threading.Lock()
        self._scroll_manager = WheelScrollManager(self)

        # Build UI — footer must be packed before body so that pack's expand
        # doesn't let the body claim all vertical space before the footer lands.
        self._build_header()
        self._build_footer()
        self._build_body()
        
        self._update_flash_steps()
        self._update_rom_folder_summary()

        # Start device polling
        self._poll_device()

        # Start background update check
        self._init_update_check()

    # ════════════════════════════════════════════════════════════════════════
    # HEADER
    # ════════════════════════════════════════════════════════════════════════
    def _build_header(self):
        header = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_secondary"],
            border_width=1,
            border_color=COLORS["border_subtle"],
            corner_radius=0,
            height=64,
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        # App title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=SPACING["lg"], pady=SPACING["sm"])

        ctk.CTkLabel(
            title_frame,
            text=APP_NAME,
            font=FONTS["heading_lg"],
            text_color=COLORS["accent_blue"],
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text=f"v{APP_VERSION}  •  {PLATFORM_NAME}",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
        ).pack(side="left", padx=(SPACING["sm"], 0))

        # Check Update button in header
        self.update_btn = ctk.CTkButton(
            title_frame,
            text="Check updates",
            font=FONTS["caption"],
            width=95,
            height=22,
            fg_color=COLORS["bg_tertiary"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            corner_radius=RADIUS["sm"],
            command=self._on_update_btn_clicked,
        )
        self.update_btn.pack(side="left", padx=(SPACING["md"], 0))

        # Circular loading spinner next to button (hidden by default)
        self.update_spinner = CircularSpinner(
            title_frame,
            size=16,
            color=COLORS["accent_blue"],
            bg=COLORS["bg_secondary"],
        )

        # Device status (right side)
        self.device_frame = ctk.CTkFrame(header, fg_color="transparent")
        self.device_frame.pack(side="right", padx=SPACING["lg"], pady=SPACING["sm"])

        self.device_dot = ctk.CTkLabel(
            self.device_frame,
            text="●",
            font=("", 16),
            text_color=COLORS["accent_red"],
            width=20,
        )
        self.device_dot.pack(side="left")

        self.device_label = ctk.CTkLabel(
            self.device_frame,
            text="No Device",
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
        )
        self.device_label.pack(side="left", padx=(SPACING["xs"], 0))

    # ════════════════════════════════════════════════════════════════════════
    # BODY (sidebar + steps)
    # ════════════════════════════════════════════════════════════════════════
    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=0, pady=0)
        body.grid_columnconfigure(0, weight=0, minsize=340)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_center(body)

    def _build_sidebar(self, parent):
        # The sidebar contains more configuration than can fit vertically on
        # a small display.  Scrolling the complete sidebar keeps Options and
        # the flash strategy reachable instead of clipping them below the
        # viewport (the image list already has its own, nested scroll area).
        sidebar = ctk.CTkScrollableFrame(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=0,
            width=340,
            scrollbar_button_color=COLORS["scrollbar_fg"],
            scrollbar_button_hover_color=COLORS["scrollbar_hover"],
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        self._scroll_manager.register(sidebar)

        # ── Bootloader Section ──
        bootloader_section = ctk.CTkFrame(sidebar, fg_color="transparent")
        bootloader_section.pack(fill="x", padx=SPACING["md"], pady=(SPACING["lg"], SPACING["sm"]))

        ctk.CTkLabel(
            bootloader_section,
            text="Bootloader",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x")

        bootloader_card = ctk.CTkFrame(
            bootloader_section,
            fg_color=COLORS["bg_tertiary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RADIUS["md"],
        )
        bootloader_card.pack(fill="x", pady=(SPACING["sm"], 0))

        self.bootloader_status_label = ctk.CTkLabel(
            bootloader_card,
            text="Connect an ADB device",
            font=FONTS["body_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.bootloader_status_label.pack(fill="x", padx=SPACING["sm"], pady=(SPACING["sm"], 0))

        self.bootloader_hint_label = ctk.CTkLabel(
            bootloader_card,
            text="Use the two actions below in order. Unlocking erases all device data.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
            justify="left",
            wraplength=280,
        )
        self.bootloader_hint_label.pack(fill="x", padx=SPACING["sm"], pady=(SPACING["xs"], SPACING["sm"]))

        self.bootloader_btn = ctk.CTkButton(
            bootloader_card,
            text="Reboot to bootloader",
            font=FONTS["body_sm"],
            height=30,
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["bg_active"],
            text_color=COLORS["text_secondary"],
            text_color_disabled=COLORS["text_secondary"],
            corner_radius=RADIUS["sm"],
            command=self._reboot_device_to_bootloader,
            state="disabled",
        )
        self.bootloader_btn.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))

        self.unlock_bootloader_btn = ctk.CTkButton(
            bootloader_card,
            text="Run fastboot flashing unlock",
            font=FONTS["body_sm"],
            height=30,
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["bg_active"],
            text_color=COLORS["text_secondary"],
            text_color_disabled=COLORS["text_secondary"],
            corner_radius=RADIUS["sm"],
            command=self._run_fastboot_unlock,
            state="disabled",
        )
        self.unlock_bootloader_btn.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))

        # ── ROM Folder Section ──
        section_rom = ctk.CTkFrame(sidebar, fg_color="transparent")
        section_rom.pack(fill="x", padx=SPACING["md"], pady=(SPACING["sm"], SPACING["sm"]))

        ctk.CTkLabel(
            section_rom,
            text="ROM folder",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x")

        self.rom_card = ctk.CTkFrame(
            section_rom,
            fg_color=COLORS["bg_tertiary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RADIUS["md"],
        )
        self.rom_card.pack(fill="x", pady=(SPACING["sm"], 0))

        self.rom_status_label = ctk.CTkLabel(
            self.rom_card,
            text="No ROM folder selected",
            font=FONTS["body_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.rom_status_label.pack(fill="x", padx=SPACING["sm"], pady=(SPACING["sm"], 0))

        self.rom_summary_host = ctk.CTkFrame(self.rom_card, fg_color="transparent")
        self.rom_summary_host.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))

        self.rom_summary_label = ctk.CTkLabel(
            self.rom_summary_host,
            text="Choose the firmware package folder before flashing.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
            justify="left",
        )
        self.rom_summary_label.pack(fill="x")

        self.script_summary_frame = ctk.CTkFrame(
            self.rom_summary_host,
            fg_color="transparent",
        )
        self.script_summary_device_label = ctk.CTkLabel(
            self.script_summary_frame,
            text="",
            font=FONTS["heading_sm"],
            text_color=COLORS["accent_blue"],
            anchor="w",
        )
        self.script_summary_device_label.pack(side="left")
        ctk.CTkLabel(
            self.script_summary_frame,
            text=" package  •  variant ",
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")
        self.script_summary_variant_label = ctk.CTkLabel(
            self.script_summary_frame,
            text="",
            font=FONTS["heading_sm"],
            text_color=COLORS["accent_purple"],
            anchor="w",
        )
        self.script_summary_variant_label.pack(side="left")
        ctk.CTkLabel(
            self.script_summary_frame,
            text="  •  ",
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")
        self.script_summary_mode_label = ctk.CTkLabel(
            self.script_summary_frame,
            text="",
            font=FONTS["caption"],
            text_color=COLORS["accent_orange"],
            anchor="w",
        )
        self.script_summary_mode_label.pack(side="left")
        self.script_summary_frame.pack_forget()

        rom_type_row = ctk.CTkFrame(self.rom_card, fg_color="transparent")
        rom_type_row.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["xs"]))

        ctk.CTkLabel(
            rom_type_row,
            text="ROM type:",
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
            width=66,
            anchor="w",
        ).pack(side="left")

        self.rom_type_combo = ctk.CTkComboBox(
            rom_type_row,
            values=[AUTO_ROM_TYPE, OFFICIAL_ROM_TYPE, JENKINS_ROM_TYPE],
            variable=self.rom_type_var,
            font=FONTS["body_sm"],
            dropdown_font=FONTS["body_sm"],
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            button_color=COLORS["bg_hover"],
            button_hover_color=COLORS["accent_blue"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_tertiary"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["bg_hover"],
            height=28,
            state="readonly",
            command=self._on_rom_type_changed,
        )
        self.rom_type_combo.pack(side="left", fill="x", expand=True, padx=(SPACING["xs"], 0))
        self.rom_type_combo.bind("<Configure>", self._on_combo_resize, add="+")
        self.after_idle(lambda: self._sync_combo_dropdown_width(self.rom_type_combo))

        self.rom_type_reset_btn = ctk.CTkButton(
            rom_type_row,
            text="Reset",
            font=FONTS["caption"],
            width=48,
            height=28,
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["primary_hover"],
            command=self._reset_rom_type,
        )
        self.rom_type_reset_btn.pack(side="right", padx=(SPACING["xs"], 0))

        self.rom_type_hint_label = ctk.CTkLabel(
            self.rom_card,
            text="The selected flash script detects Official/Jenkins automatically.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
            justify="left",
        )
        self.rom_type_hint_label.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))

        rom_row = ctk.CTkFrame(self.rom_card, fg_color="transparent")
        rom_row.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))

        self.rom_entry = ctk.CTkEntry(
            rom_row,
            placeholder_text="Select ROM folder...",
            font=FONTS["body_sm"],
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            height=34,
        )
        self.rom_entry.pack(side="left", fill="x", expand=True, padx=(0, SPACING["sm"]))
        
        # Bind events so pasting or typing a path works without clicking Browse
        self.rom_entry.bind("<Return>", lambda e: self._on_rom_entry_changed())
        self.rom_entry.bind("<FocusOut>", lambda e: self._on_rom_entry_changed())

        self.browse_btn = ctk.CTkButton(
            rom_row,
            text="Browse",
            font=FONTS["body_sm"],
            width=70,
            height=34,
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["on_accent"],
            corner_radius=RADIUS["sm"],
            command=self._browse_rom,
        )
        self.browse_btn.pack(side="right")

        # ── Variant/Region Selection ──
        self.region_row = ctk.CTkFrame(section_rom, fg_color="transparent")
        
        ctk.CTkLabel(
            self.region_row,
            text="Variant:",
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
            width=60,
            anchor="w",
        ).pack(side="left")

        self.region_combo = ctk.CTkComboBox(
            self.region_row,
            values=["— none —"],
            font=FONTS["body_sm"],
            dropdown_font=FONTS["body_sm"],
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            button_color=COLORS["bg_hover"],
            button_hover_color=COLORS["accent_blue"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_tertiary"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["bg_hover"],
            height=28,
            state="readonly",
            command=self._on_region_selected,
        )
        self.region_combo.pack(side="left", fill="x", expand=True, padx=(SPACING["xs"], 0))
        self.region_combo.bind("<Configure>", self._on_combo_resize, add="+")

    def _build_center(self, parent):
        center = ctk.CTkFrame(parent, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew")
        center.grid_rowconfigure(0, weight=1)
        center.grid_rowconfigure(1, weight=0, minsize=136)
        center.grid_columnconfigure(0, weight=1)

        # ── Steps Panel ──
        steps_panel = ctk.CTkFrame(center, fg_color="transparent")
        steps_panel.grid(row=0, column=0, sticky="nsew", padx=SPACING["md"], pady=(SPACING["md"], 0))

        steps_header = ctk.CTkFrame(steps_panel, fg_color="transparent", height=28)
        steps_header.pack(fill="x", pady=(0, SPACING["sm"]))
        steps_header.pack_propagate(False)

        ctk.CTkLabel(
            steps_header,
            text="Flash steps",
            font=FONTS["heading_md"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left")

        self.steps_count_label = ctk.CTkLabel(
            steps_header,
            text="0 steps",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="e",
        )
        self.steps_count_label.pack(side="right", padx=(SPACING["sm"], 0))

        self.steps_scroll = ctk.CTkScrollableFrame(
            steps_panel,
            fg_color="transparent",
            scrollbar_button_color=COLORS["scrollbar_fg"],
            scrollbar_button_hover_color=COLORS["scrollbar_hover"],
        )
        self.steps_scroll.pack(fill="both", expand=True)
        self._scroll_manager.register(self.steps_scroll)

        for step in self.flash_steps:
            w = StepWidget(self.steps_scroll, step.id, step.name)
            w.pack(fill="x", pady=2)
            self.step_widgets[step.id] = w

        # ── Log Panel ──
        log_frame = ctk.CTkFrame(center, fg_color="transparent")
        log_frame.grid(row=1, column=0, sticky="nsew", padx=SPACING["md"], pady=SPACING["md"])

        self.log_panel = LogPanel(log_frame)
        self.log_panel.pack(fill="both", expand=True)

    # ════════════════════════════════════════════════════════════════════════
    # FOOTER (Action Bar)
    # ════════════════════════════════════════════════════════════════════════
    def _build_footer(self):
        footer = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_secondary"],
            border_width=1,
            border_color=COLORS["border_subtle"],
            corner_radius=0,
        )
        footer.pack(fill="x", side="bottom", ipady=SPACING["xs"])

        self.flash_action_btn = ctk.CTkButton(
            footer,
            text="Start flash",
            font=FONTS["heading_md"],
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["on_accent"],
            height=52,
            width=210,
            corner_radius=RADIUS["lg"],
            command=self._start_flash,
        )
        self.flash_action_btn.pack(side="right", padx=SPACING["lg"])

        self.suw_btn = ctk.CTkButton(
            footer,
            text="Skip Setup Wizard",
            font=FONTS["heading_md"],
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["bg_active"],
            text_color=COLORS["text_primary"],
            text_color_disabled=COLORS["text_muted"],
            height=52,
            width=180,
            corner_radius=RADIUS["md"],
            command=self._run_suw_only,
            state="disabled",
        )
        self.suw_btn.pack(side="right", padx=(0, SPACING["sm"]))

        # Status text
        self.status_label = ctk.CTkLabel(
            footer,
            text="Ready — Select ROM folder and connect device",
            font=FONTS["body_sm"],
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.status_label.pack(side="left", padx=SPACING["lg"])

        # Total elapsed timer
        self.total_timer_label = ctk.CTkLabel(
            footer,
            text="",
            font=FONTS["body_sm"],
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.total_timer_label.pack(side="left", padx=(0, SPACING["md"]))
        self._flash_start_time: float | None = None
        self._total_timer_id = None

    # ════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ════════════════════════════════════════════════════════════════════════
    def _on_rom_entry_changed(self):
        """Triggered when the user types or pastes a path and hits Enter or leaves the text box."""
        path = self.rom_entry.get().strip()
        if path and os.path.exists(path) and path != getattr(self, "_last_scanned_path", ""):
            self._scan_rom_path(path)

    def _browse_rom(self):
        """Open folder dialog to select ROM directory."""
        path = self._select_rom_folder()
        if not path:
            return

        self.rom_entry.delete(0, "end")
        self.rom_entry.insert(0, path)
        self._scan_rom_path(path)

    def _select_rom_folder(self) -> str:
        """Select a ROM folder using the most reliable dialog for the platform."""
        if sys.platform.startswith("linux"):
            path = self._select_rom_folder_with_zenity()
            if path is not None:
                return path

        return filedialog.askdirectory(
            title="Select ROM Folder",
            parent=self,
            initialdir=self.rom_path or os.path.expanduser("~"),
        )

    def _select_rom_folder_with_zenity(self) -> str | None:
        zenity = shutil.which("zenity")
        if not zenity:
            return None

        # Clean environment under PyInstaller to prevent Zenity from crashing
        # due to library version mismatch (e.g. GLib/GTK)
        env = get_clean_env()

        initial_dir = self.rom_path or os.path.expanduser("~")
        try:
            result = subprocess.run(
                [
                    zenity,
                    "--file-selection",
                    "--directory",
                    "--title=Select ROM Folder",
                    f"--filename={os.path.join(initial_dir, '')}",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
        except Exception:
            return None

        # Zenity return codes:
        # 0 = OK (directory selected)
        # 1 = Cancel/Close (user dismissed dialog)
        # Anything else = Crash or error, fall back to filedialog
        if result.returncode == 1:
            return ""
        elif result.returncode != 0:
            return None

        return result.stdout.strip()
        
    def _scan_rom_path(self, path: str):
        """Scan a firmware folder and resolve its supported flash profile."""
        self.rom_path = path
        self._last_scanned_path = path
        # Model selection is internal now; every new package starts from the
        # automatic resolver so a previous ROM cannot leak into this scan.
        self.current_model.set(AUTO_DETECT_LABEL)
        self.detected_images = scan_rom_folder(path)
        self.selected_images = {}
        self.selected_g6_variant = None
        self.use_super = False

        # Auto-detect device when in auto mode
        if self.current_model.get() == AUTO_DETECT_LABEL:
            detected = detect_device(path)
            if detected:
                self.auto_detected_device = detected
                self.current_model.set(detected)
                self.auto_detected_variant = detect_variant(path, detected, self.SCRIPT_PROFILES)
                if self.auto_detected_variant:
                    self.selected_script_variants[detected] = self.auto_detected_variant
                detected_label = G6_FAMILY_LABEL if detected in G6_FAMILY_MODELS else detected
                self.log_panel.append(
                    f"🔍 Auto-detected profile: {detected_label}"
                    + (f" ({self.auto_detected_variant})" if self.auto_detected_variant else "")
                )
            else:
                self.auto_detected_device = None
                self.auto_detected_variant = None
                self.log_panel.append("⚠️ Could not auto-detect device from ROM folder")

        if self.current_model.get() in G6_FAMILY_MODELS:
            variants = get_g6_variants(self.detected_images)
            self.selected_g6_variant = variants[0] if variants else None
            self.selected_images = resolve_g6_images(
                self.detected_images,
                self.selected_g6_variant,
            )

        self._update_region_visibility()
        self._update_rom_folder_summary()
        self.log_panel.append(f"📁 ROM folder: {path}")
        self._update_flash_steps()
        self._update_super_strategy()

    def _update_rom_folder_summary(self):
        """Refresh folder card status after scan or model change."""
        if not self.rom_path:
            self.rom_status_label.configure(
                text="No ROM folder selected",
                text_color=COLORS["text_primary"],
            )
            self.script_summary_frame.pack_forget()
            self.rom_summary_label.pack(fill="x")
            self.rom_summary_label.configure(
                text="Choose the firmware package folder before flashing.",
                text_color=COLORS["text_muted"],
            )
            return

        folder_name = os.path.basename(os.path.normpath(self.rom_path)) or self.rom_path
        self.rom_status_label.configure(
            text=f"Selected: {folder_name}",
            text_color=COLORS["accent_green"],
        )

        script_device = self._resolve_script_device()
        if script_device:
            variants = self._get_script_variant_options(script_device)
            selected_variant = self.selected_script_variants.get(script_device, variants[0])
            default_args = self.SCRIPT_PROFILES[script_device].get("default_args", [])
            wipe_label = "wipe data enabled" if "--wipe" in default_args else "dirty flash"
            self.rom_summary_label.pack_forget()
            self.script_summary_device_label.configure(text=script_device)
            self.script_summary_variant_label.configure(text=selected_variant.upper())
            self.script_summary_mode_label.configure(text=wipe_label)
            self.script_summary_frame.pack(fill="x")
            return

        self.script_summary_frame.pack_forget()
        self.rom_summary_label.pack(fill="x")
        if self.current_model.get() in G6_FAMILY_MODELS:
            variant = f" • variant {self.selected_g6_variant}" if self.selected_g6_variant else ""
            summary = f"{G6_FAMILY_LABEL} flash mode{variant} • images selected automatically"
        else:
            summary = "Select a supported firmware package folder."
        self.rom_summary_label.configure(
            text=summary,
            text_color=COLORS["text_secondary"],
        )

    def _on_rom_type_changed(self, choice: str):
        """Apply a script ROM source override, or leave detection to the script."""
        self.selected_rom_type = "" if choice == AUTO_ROM_TYPE else choice.lower()
        self._update_rom_type_ui()
        if choice == AUTO_ROM_TYPE:
            self.log_panel.append("🔍 ROM type: script auto-detection")
        else:
            self.log_panel.append(f"🛠 ROM type override: {choice}")
        self._update_flash_steps()

    def _reset_rom_type(self):
        """Return ROM type selection to automatic detection."""
        if hasattr(self, "rom_type_combo"):
            self.rom_type_var.set(AUTO_ROM_TYPE)
        self.selected_rom_type = ""
        if hasattr(self, "rom_type_hint_label"):
            self._update_rom_type_ui()
        self._update_flash_steps()

    def _update_rom_type_ui(self):
        """Show whether ROM source detection is delegated to the script."""
        if not hasattr(self, "rom_type_hint_label"):
            return
        if self.rom_type_var.get() == AUTO_ROM_TYPE:
            self.rom_type_hint_label.configure(
                text="Script will auto-detect Official/Jenkins from ROM contents.",
                text_color=COLORS["accent_green"],
            )
            return
        self.rom_type_hint_label.configure(
            text=f"Manual override passed to script: {self.rom_type_var.get().lower()}",
            text_color=COLORS["accent_orange"],
        )

    def _update_region_visibility(self):
        """Show the relevant variant row for script or G6-family profiles."""
        if self._resolve_script_device():
            self._configure_script_variant_selector()
        elif self.current_model.get() in G6_FAMILY_MODELS:
            self._configure_g6_variant_selector()
        else:
            self.region_row.pack_forget()

    def _on_combo_resize(self, event):
        """Keep CustomTkinter dropdown menus as wide as their combo box."""
        self._sync_combo_dropdown_width(event.widget)

    def _sync_combo_dropdown_width(self, combo):
        """Resize a combo dropdown to match the visible combo width."""
        dropdown = getattr(combo, "_dropdown_menu", None)
        width = combo.winfo_width()
        if dropdown is None or width <= 1:
            return

        menu_font = tkfont.Font(root=combo, font=combo.cget("dropdown_font"))
        try:
            padding_width = max(menu_font.measure("\u2007"), 1)
            padding_count = max(2, int(width / padding_width) - 1)
            labels = []
            for value in dropdown.cget("values"):
                value_text = str(value)
                labels.append(
                    "\u2007\u2007" + value_text + "".join("\u2007" for _ in range(padding_count))
                )
        finally:
            del menu_font

        # Tk ignores trailing regular spaces when calculating Menu width, while
        # figure spaces retain their measured width. Rebuild commands first,
        # then replace labels with width-preserving padding.
        dropdown._add_menu_commands()
        for index, label in enumerate(labels):
            dropdown.entryconfigure(index, label=label)

    def _set_variant_selector(self, values: list[str], selected: str):
        """Show the shared Variant row with the provided values."""
        selected_value = selected if selected in values else values[0]
        self.region_combo.configure(values=values)
        self.region_combo.set(selected_value)
        self.region_row.pack(fill="x", pady=(SPACING["sm"], 0))
        self.region_row.update_idletasks()
        self._sync_combo_dropdown_width(self.region_combo)

    def _resolve_script_device(self) -> str | None:
        """Return the actual script device name, or None if not in script mode."""
        current_model = self.current_model.get()
        if current_model in self.SCRIPT_PROFILES:
            return current_model
        if current_model == AUTO_DETECT_LABEL and self.auto_detected_device:
            return self.auto_detected_device
        return None

    def _get_script_variant_options(self, device: str) -> list[str]:
        """Return script variants, preferring folders present in the selected ROM."""
        config = self.SCRIPT_PROFILES[device]
        if not self.rom_path:
            return config["variants"]

        detected = [
            variant
            for variant in config["variants"]
            if os.path.isdir(os.path.join(self.rom_path, config["variant_dirs"][variant]))
        ]
        return detected or config["variants"]

    def _configure_script_variant_selector(self):
        """Show fixed script variants for PS11/E11/E10 or auto-detected profiles."""
        device = self._resolve_script_device()
        if not device:
            self.region_row.pack_forget()
            return

        config = self.SCRIPT_PROFILES[device]
        values = self._get_script_variant_options(device)
        selected_variant = self.selected_script_variants.get(
            device,
            config["default_variant"],
        )

        if selected_variant not in values:
            selected_variant = config["default_variant"] if config["default_variant"] in values else values[0]
            self.selected_script_variants[device] = selected_variant

        self._set_variant_selector(values, selected_variant)

    def _configure_g6_variant_selector(self):
        """Show regional image directories for the shared G6-family profile."""
        values = get_g6_variants(self.detected_images)
        if not values:
            self.region_row.pack_forget()
            return

        selected_variant = self.selected_g6_variant if self.selected_g6_variant in values else values[0]
        self.selected_g6_variant = selected_variant
        self._set_variant_selector(values, selected_variant)

    def _on_region_selected(self, choice: str):
        """Update the selected script or G6-family image variant."""
        script_device = self._resolve_script_device()
        if script_device:
            self.selected_script_variants[script_device] = choice
            self.log_panel.append(f"🌍 Selected Variant: {choice}")
            self._update_rom_folder_summary()
            self._update_flash_steps()
            return

        if self.current_model.get() not in G6_FAMILY_MODELS:
            return

        variants = get_g6_variants(self.detected_images)
        if choice not in variants:
            return
        self.selected_g6_variant = choice
        self.selected_images = resolve_g6_images(self.detected_images, choice)
        self.log_panel.append(f"🌍 Selected Variant: {choice}")
        self._update_rom_folder_summary()

    def _set_flash_action_running(self):
        """Turn the fixed footer action into the flash stop control."""
        self.flash_action_btn.configure(
            text="Stop",
            fg_color=COLORS["accent_red"],
            hover_color=COLORS["danger_hover"],
            text_color=COLORS["on_accent"],
            width=210,
            command=self._stop_flash,
        )

    def _set_flash_action_idle(self):
        """Restore the fixed footer action to Start flash."""
        self.flash_action_btn.configure(
            text="Start flash",
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["on_accent"],
            width=210,
            command=self._start_flash,
        )

    def _start_flash(self):
        """Validate and start the flash process."""
        # Validate ROM folder
        if not self.rom_path or not os.path.isdir(self.rom_path):
            show_error(self, "Cannot start flash", "Please select a valid ROM folder first.")
            return

        # Validate required images based on the shared G6-family profile.
        current_model = self.current_model.get()

        if current_model in G6_FAMILY_MODELS:
            if self.use_super:
                required = ["super"]
                optional_with_steps = ["vbmeta"]
            else:
                required = ["system"]  # system.img is always required
                optional_with_steps = ["vbmeta", "product", "system_ext"]
        else:
            script_device = self._resolve_script_device()
            if not script_device:
                if current_model == AUTO_DETECT_LABEL:
                    show_error(
                        self,
                        "Device not detected",
                        "Could not auto-detect device from ROM folder.\n\n"
                        "The folder must contain device-specific files or variant directories.",
                    )
                else:
                    show_error(self, "Unknown model", f"Unknown model: {current_model}")
                return

            required = []
            optional_with_steps = []
            script_name = self.SCRIPT_PROFILES[script_device]["script"]
            app_root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            script_candidates = [
                os.path.join(app_root, script_name),
                os.path.join(self.rom_path, script_name),
            ]
            if not any(os.path.isfile(path) for path in script_candidates):
                show_error(self, "Flash script missing", f"Flash script not found: {script_name}")
                return

        for key in required:
            if key not in self.selected_images:
                show_error(
                    self,
                    "Required image missing",
                    f"Required image not found: {key}\nPlease check the ROM folder.",
                )
                return

        # Warn about missing optional images
        missing_optional = [k for k in optional_with_steps if k not in self.selected_images]
        if missing_optional:
            msg = f"The following images were not detected:\n{', '.join(missing_optional)}\n\nSteps using these images will fail.\nContinue anyway?"
            if not ask_yes_no(self, "Warning", msg):
                return

        script_device = self._resolve_script_device()
        if script_device:
            selected_variant = self.selected_script_variants.get(script_device, self.SCRIPT_PROFILES[script_device]["default_variant"])
            script_display = self.SCRIPT_PROFILES[script_device]["script"]
            default_args = self.SCRIPT_PROFILES[script_device].get("default_args", [])
            data_note = "⚠️  This will ERASE all data on the device!" if "--wipe" in default_args \
                else "⚠️  Dirty flash — user data will be PRESERVED."
            display_model = current_model if current_model != AUTO_DETECT_LABEL else f"{script_device} (auto-detected)"
            msg = (
                f"Ready to flash {display_model} device.\n\n"
                f"Firmware folder: {self.rom_path}\n"
                f"ROM type: {self.rom_type_var.get()} (script detection/override)\n"
                f"Script: {script_display}\n"
                f"Variant: {selected_variant}\n\n"
                f"{data_note}\n\n"
                f"Continue?"
            )
        else:
            msg = (
                f"Ready to flash {G6_FAMILY_LABEL}.\n\n"
                f"ROM: {self.rom_path}\n"
                "Images will be selected automatically from the folder.\n"
                f"ROM type: {self.rom_type_var.get()}\n\n"
                f"⚠️  This will ERASE all data on the device!\n\n"
                f"Continue?"
            )
        if not ask_yes_no(self, "Confirm Flash", msg):
            return

        # Device mode may have changed after the ROM was selected (for example
        # after pressing Reboot to bootloader), so refresh mode-dependent steps.
        self._update_flash_steps()

        # Reset step widgets
        for step in self.flash_steps:
            step.status = StepStatus.PENDING
            step.progress = 0.0
            step.elapsed = 0.0
            step.output = ""
        for w in self.step_widgets.values():
            w.update_status("pending")

        # Start total timer
        import time as _time
        self._flash_start_time = _time.time()
        self._tick_total_timer()

        # Update the fixed footer action — Start → Stop.
        self._set_flash_action_running()
        self._lock_controls()
        self.status_label.configure(
            text="Flashing in progress...",
            text_color=COLORS["accent_orange"],
        )
        self.total_timer_label.configure(text="Elapsed: 0:00", text_color=COLORS["text_muted"])

        steps = self.flash_steps

        # Start worker
        self.worker = FlashWorker(
            steps=steps,
            rom_path=self.rom_path,
            detected_images=self.selected_images,
            on_progress=self._on_flash_progress,
            on_log=self._on_flash_log,
            on_finished=self._on_flash_finished,
        )
        self.worker.start()

    def _stop_flash(self):
        """Stop the flash process."""
        if self.worker and self.worker.is_alive():
            if ask_yes_no(self, "Confirm", "Stop flashing? This may leave your device in an unstable state."):
                self.worker.stop()

    def _run_suw_only(self):
        """Mark an ADB device as provisioned and reboot past Android SUW."""
        if self.device_state != "adb" or not self.device_serial:
            show_error(
                self,
                "ADB device required",
                "Connect and authorize the device through ADB before skipping Setup Wizard.",
            )
            return

        if not ask_yes_no(
            self,
            "Skip Setup Wizard",
            "This marks the connected device as provisioned and reboots it.\n\n"
            "The Android Setup Wizard will be bypassed on the next boot.\n\n"
            "Continue?",
        ):
            return

        suw_steps = build_suw_only_steps()
        self.flash_steps = suw_steps
        self._rebuild_step_widgets()
        for step in suw_steps:
            step.status = StepStatus.PENDING
            step.progress = 0.0
            step.elapsed = 0.0
            step.output = ""
        for widget in self.step_widgets.values():
            widget.update_status("pending")

        self._set_flash_action_running()
        self._lock_controls()
        self.status_label.configure(
            text="Skipping Setup Wizard...",
            text_color=COLORS["accent_orange"],
        )
        self.total_timer_label.configure(text="")

        self.worker = FlashWorker(
            steps=suw_steps,
            rom_path="",
            detected_images={},
            on_progress=self._on_flash_progress,
            on_log=self._on_flash_log,
            on_finished=self._on_suw_finished,
        )
        self.worker.start()

    def _on_suw_finished(self, success: bool):
        """Handle completion of the standalone SUW action."""
        self.after(0, self._finish_suw, success)

    def _finish_suw(self, success: bool):
        """Restore the normal flash UI after the standalone SUW action."""
        self._set_flash_action_idle()
        self._unlock_controls()
        self._update_flash_steps()

        if success:
            self.status_label.configure(
                text="Setup Wizard skipped — device is rebooting",
                text_color=COLORS["accent_green"],
            )
            show_info(self, "Setup Wizard skipped", "The device is marked as provisioned and is rebooting.")
        else:
            self.status_label.configure(
                text="Setup Wizard skip failed or stopped",
                text_color=COLORS["accent_red"],
            )

    def _tick_total_timer(self):
        """Tick the total elapsed timer every second while flashing."""
        import time as _time
        if self._flash_start_time is None:
            return
        elapsed = _time.time() - self._flash_start_time
        minutes = int(elapsed) // 60
        seconds = int(elapsed) % 60
        self.total_timer_label.configure(text=f"Elapsed: {minutes}:{seconds:02d}")
        self._total_timer_id = self.after(1000, self._tick_total_timer)

    def _update_flash_steps(self):
        """Update steps based on the selected model and detected ROM files."""
        current_model = self.current_model.get()

        if current_model in G6_FAMILY_MODELS:
            self.flash_steps = build_g6_ramba_steps(use_super=self.use_super)
        else:
            script_device = self._resolve_script_device()
            if script_device:
                config = self.SCRIPT_PROFILES[script_device]
                selected_variant = self.selected_script_variants.get(script_device, config["default_variant"])
                script_name = config["script"]
                script_args = [config["variant_arg"], selected_variant] + config["default_args"]
                if self.selected_rom_type:
                    script_args += ["--rom-type", self.selected_rom_type]
                self.flash_steps = build_script_device_steps(
                    script_device,
                    script_name,
                    script_args,
                )
            else:
                self.flash_steps = []
        self._rebuild_step_widgets()
        if hasattr(self, "steps_count_label"):
            step_count = len(self.flash_steps)
            self.steps_count_label.configure(
                text=f"{step_count} step{'s' if step_count != 1 else ''}",
            )

    def _lock_controls(self):
        """Disable all configuration controls during flashing."""
        self._poll_running = False
        if hasattr(self, "_poll_after_id") and self._poll_after_id:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None

        self.rom_entry.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        self.rom_type_combo.configure(state="disabled")
        self.rom_type_reset_btn.configure(state="disabled")
        self.region_combo.configure(state="disabled")
        self.bootloader_btn.configure(state="disabled")
        self.unlock_bootloader_btn.configure(state="disabled")
        self.suw_btn.configure(state="disabled")

    def _unlock_controls(self):
        """Re-enable configuration controls after flashing completes."""
        self._poll_running = True
        self._poll_device()

        self.rom_entry.configure(state="normal")
        self.browse_btn.configure(state="normal")
        self.rom_type_combo.configure(state="readonly")
        self.rom_type_reset_btn.configure(state="normal")
        self.region_combo.configure(state="readonly")
        self._update_bootloader_ui(self.device_state, self.device_serial)

    def _rebuild_step_widgets(self):
        """Destroy and re-create step widgets to reflect the current step list."""
        # Remove all existing widgets
        for w in self.step_widgets.values():
            w.destroy()
        self.step_widgets.clear()

        # Recreate from the updated flash_steps
        for step in self.flash_steps:
            w = StepWidget(self.steps_scroll, step.id, step.name)
            w.pack(fill="x", pady=2)
            self.step_widgets[step.id] = w

    def _update_super_strategy(self):
        """Detect super.img selection and switch flash strategy automatically."""
        if self.current_model.get() not in G6_FAMILY_MODELS:
            return

        self.use_super = "super" in self.selected_images
        self._update_flash_steps()

    def _on_flash_progress(self, progress: FlashProgress):
        """Handle progress update from worker (called from background thread)."""
        self.after(0, self._update_step_ui, progress)

    def _on_flash_log(self, message: str):
        """Handle log message from worker (called from background thread)."""
        self.after(0, self.log_panel.append, message)

    def _on_flash_finished(self, success: bool):
        """Handle flash completion (called from background thread)."""
        self.after(0, self._finish_flash, success)

    def _update_step_ui(self, progress: FlashProgress):
        """Update step widget from main thread."""
        widget = self.step_widgets.get(progress.step_id)
        if widget:
            widget.update_status(
                progress.status.value,
                progress.progress,
                progress.message,
                elapsed=progress.elapsed,
            )

    def _finish_flash(self, success: bool):
        """Handle flash completion in main thread."""
        # Stop total timer
        import time as _time
        if self._total_timer_id:
            self.after_cancel(self._total_timer_id)
            self._total_timer_id = None
        total_elapsed = (_time.time() - self._flash_start_time) if self._flash_start_time else 0.0
        self._flash_start_time = None
        mins = int(total_elapsed) // 60
        secs = int(total_elapsed) % 60
        total_str = f"{mins}:{secs:02d}" if mins else f"{total_elapsed:.1f}s"

        self._set_flash_action_idle()
        self._unlock_controls()

        if success:
            self.status_label.configure(
                text="✓ Flash completed successfully!",
                text_color=COLORS["accent_green"],
            )
            self.total_timer_label.configure(
                text=f"Elapsed: {total_str}",
                text_color=COLORS["accent_green"],
            )
            show_info(
                self,
                "Flash completed",
                f"ROM flashed successfully.\nTotal time: {total_str}\nDevice is rebooting.",
            )
        else:
            self.status_label.configure(
                text="× Flash failed or stopped",
                text_color=COLORS["accent_red"],
            )
            self.total_timer_label.configure(
                text=f"Stopped at: {total_str}",
                text_color=COLORS["accent_red"],
            )

    # ════════════════════════════════════════════════════════════════════════
    # DEVICE POLLING
    # ════════════════════════════════════════════════════════════════════════
    def _poll_device(self):
        """Poll device state every 3 seconds."""
        if not self._poll_running:
            return

        def check():
            if not self._device_poll_lock.acquire(blocking=False):
                return
            try:
                state, serial = get_device_state()
                self.after(0, self._update_device_ui, state, serial)
            finally:
                self._device_poll_lock.release()

        if hasattr(self, "_poll_after_id") and self._poll_after_id:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None

        threading.Thread(target=check, daemon=True).start()
        self._poll_after_id = self.after(3000, self._poll_device)

    def _update_device_ui(self, state: str, serial: str | None):
        """Update device status display."""
        self.device_state = state
        self.device_serial = serial

        if state in ("fastboot", "adb") and serial:
            device_key = (state, serial)
            cached_key = (self.unlock_status_mode, self.unlock_status_serial)
            if device_key != cached_key and self._unlock_status_pending_key != device_key:
                self.unlock_status = None
                self._check_bootloader_unlock_status(state, serial)
        else:
            self.unlock_status = None
            self.unlock_status_serial = None
            self.unlock_status_mode = None
            self._unlock_status_pending = False
            self._unlock_status_pending_key = None

        if state == "fastboot":
            self.device_dot.configure(text_color=COLORS["accent_green"])
            self.device_label.configure(
                text=f"Fastboot: {serial}",
                text_color=COLORS["accent_green"],
            )
        elif state == "adb":
            self.device_dot.configure(text_color=COLORS["accent_yellow"])
            self.device_label.configure(
                text=f"ADB: {serial}",
                text_color=COLORS["accent_yellow"],
            )
        else:
            self.device_dot.configure(text_color=COLORS["accent_red"])
            self.device_label.configure(
                text="No Device",
                text_color=COLORS["text_muted"],
            )

        self._update_bootloader_ui(state, serial)

    def _check_bootloader_unlock_status(self, state: str, serial: str):
        """Read the unlock flag without blocking the UI thread."""
        request_key = (state, serial)
        if self._unlock_status_pending_key == request_key:
            return
        self._unlock_status_pending = True
        self._unlock_status_pending_key = request_key

        def check():
            if state == "adb":
                status, detail = get_adb_bootloader_unlock_status(serial)
            else:
                status, detail = get_bootloader_unlock_status(serial)
            self.after(0, self._finish_bootloader_unlock_status, state, serial, status, detail)

        threading.Thread(target=check, daemon=True).start()

    def _finish_bootloader_unlock_status(
        self,
        state: str,
        serial: str,
        status: bool | None,
        detail: str,
    ):
        request_key = (state, serial)
        if self._unlock_status_pending_key == request_key:
            self._unlock_status_pending = False
            self._unlock_status_pending_key = None
        if self.device_state != state or self.device_serial != serial:
            return

        self.unlock_status_serial = serial
        self.unlock_status_mode = state
        self.unlock_status = status
        if status is True:
            self.log_panel.append("Bootloader status: already unlocked")
        elif status is False:
            self.log_panel.append("Bootloader status: locked")
        elif detail:
            self.log_panel.append(f"Could not read bootloader unlock status: {detail}")
        self._update_bootloader_ui(self.device_state, self.device_serial)

    def _update_bootloader_ui(self, state: str, serial: str | None):
        """Keep the bootloader action aligned with the current device mode."""
        if not hasattr(self, "bootloader_status_label"):
            return

        disabled_button = {
            "state": "disabled",
            "fg_color": COLORS["bg_hover"],
            "hover_color": COLORS["bg_active"],
            "text_color": COLORS["text_secondary"],
            "text_color_disabled": COLORS["text_secondary"],
        }
        self.bootloader_btn.configure(**disabled_button)
        self.unlock_bootloader_btn.configure(**disabled_button)
        self.suw_btn.configure(state="disabled")

        if state == "adb" and serial:
            status_known = (
                self.unlock_status_mode == "adb"
                and self.unlock_status_serial == serial
            )
            if status_known and self.unlock_status is True:
                status_text = "ADB connected · bootloader unlocked"
                status_color = COLORS["accent_green"]
                hint_text = "Bootloader is already unlocked. Reboot to bootloader when ready to flash."
                unlock_text = "Already unlocked"
            elif status_known and self.unlock_status is False:
                status_text = "ADB connected · bootloader locked"
                status_color = COLORS["accent_yellow"]
                hint_text = "Reboot to bootloader, then run the unlock command. It erases all data."
                unlock_text = "Unlock after rebooting"
            elif self._unlock_status_pending:
                status_text = "ADB connected · checking bootloader"
                status_color = COLORS["accent_yellow"]
                hint_text = "Reading the bootloader lock status from Android..."
                unlock_text = "Checking unlock status..."
            else:
                status_text = "ADB connected"
                status_color = COLORS["accent_green"]
                hint_text = "Step 1: reboot to bootloader. The unlock action becomes available next."
                unlock_text = "Run fastboot flashing unlock"
            self.bootloader_status_label.configure(
                text=status_text,
                text_color=status_color,
            )
            self.bootloader_btn.configure(
                text="Reboot to bootloader",
                fg_color=COLORS["accent_blue"],
                hover_color=COLORS["primary_hover"],
                text_color=COLORS["on_accent"],
            )
            self.bootloader_hint_label.configure(
                text=hint_text
            )
            self.unlock_bootloader_btn.configure(text=unlock_text)
            self.bootloader_btn.configure(state="normal")
            self.suw_btn.configure(
                fg_color=COLORS["bg_hover"],
                hover_color=COLORS["bg_active"],
                text_color=COLORS["text_primary"],
                state="normal",
            )
        elif state == "fastboot" and serial:
            self.bootloader_btn.configure(text="Already in bootloader")
            status_known = (
                self.unlock_status_mode == "fastboot"
                and self.unlock_status_serial == serial
            )
            if status_known and self.unlock_status is True:
                self.bootloader_status_label.configure(
                    text="Bootloader unlocked",
                    text_color=COLORS["accent_green"],
                )
                self.bootloader_hint_label.configure(
                    text="Bootloader is already unlocked. You can start flashing now."
                )
                self.unlock_bootloader_btn.configure(text="Already unlocked")
            elif self._unlock_status_pending:
                self.bootloader_status_label.configure(
                    text="Checking bootloader status...",
                    text_color=COLORS["accent_yellow"],
                )
                self.bootloader_hint_label.configure(text="Reading the device unlock status...")
                self.unlock_bootloader_btn.configure(text="Checking unlock status...")
            else:
                status_text = "Bootloader locked" if self.unlock_status is False else "Unlock status unavailable"
                status_color = COLORS["accent_yellow"] if self.unlock_status is False else COLORS["text_muted"]
                self.bootloader_status_label.configure(text=status_text, text_color=status_color)
                self.bootloader_hint_label.configure(
                    text=(
                        "Run unlock and confirm on the device. This erases all data."
                        if self.unlock_status is False
                        else "Could not verify the unlock flag. You can try the unlock command manually."
                    )
                )
                self.unlock_bootloader_btn.configure(
                    text="Run fastboot flashing unlock",
                    fg_color=COLORS["accent_orange"],
                    hover_color=COLORS["warning_hover"],
                    text_color=COLORS["on_accent"],
                    state="normal",
                )
        else:
            self.bootloader_status_label.configure(
                text="No device",
                text_color=COLORS["text_muted"],
            )
            self.bootloader_hint_label.configure(
                text="Connect an authorized ADB device to reboot, or a fastboot device to unlock."
            )
            self.bootloader_btn.configure(text="Reboot to bootloader")
            self.unlock_bootloader_btn.configure(text="Run fastboot flashing unlock")

    def _reboot_device_to_bootloader(self):
        """Enter the bootloader through the connected ADB device."""
        serial = self.device_serial
        if self.device_state != "adb" or not serial:
            return

        self.bootloader_btn.configure(state="disabled")

        def run_reboot():
            success, detail = reboot_to_bootloader(serial)
            self.after(0, self._finish_reboot_to_bootloader, success, detail)

        threading.Thread(target=run_reboot, daemon=True).start()

    def _finish_reboot_to_bootloader(self, success: bool, detail: str):
        if success:
            self.log_panel.append("Rebooting device to bootloader")
            self.bootloader_status_label.configure(
                text="Rebooting to bootloader…",
                text_color=COLORS["accent_yellow"],
            )
        else:
            self.log_panel.append(f"Could not enter bootloader: {detail or 'ADB command failed'}")
            show_error(
                self,
                "Bootloader action failed",
                "Could not reboot the device into bootloader mode.\n\n"
                f"{detail or 'Make sure the device is authorized and connected via ADB.'}",
            )
            self._update_bootloader_ui(self.device_state, self.device_serial)

    def _run_fastboot_unlock(self):
        """Run fastboot flashing unlock after an explicit data-loss confirmation."""
        serial = self.device_serial
        if self.device_state != "fastboot" or not serial:
            return

        if (
            self.unlock_status_mode == "fastboot"
            and self.unlock_status_serial == serial
            and self.unlock_status is True
        ):
            show_info(
                self,
                "Bootloader already unlocked",
                "This device is already unlocked. You can start flashing now.",
            )
            return

        confirmed = ask_yes_no(
            self,
            "Unlock bootloader",
            "This runs fastboot flashing unlock on the connected device.\n\n"
            "The device will erase all user data and may reboot. Confirm the unlock prompt on the device if shown.\n\n"
            "Continue?",
        )
        if not confirmed:
            return

        self.unlock_bootloader_btn.configure(state="disabled")
        self.bootloader_status_label.configure(
            text="Unlocking bootloader…",
            text_color=COLORS["accent_orange"],
        )

        def run_unlock():
            success, detail = unlock_bootloader(serial)
            self.after(0, self._finish_fastboot_unlock, serial, success, detail)

        threading.Thread(target=run_unlock, daemon=True).start()

    def _finish_fastboot_unlock(self, serial: str, success: bool, detail: str):
        if success:
            self.log_panel.append("fastboot flashing unlock completed")
            self.unlock_status = True
            self.unlock_status_serial = serial
            self.unlock_status_mode = "fastboot"
            self._unlock_status_pending = False
            self._unlock_status_pending_key = None
            self.bootloader_status_label.configure(
                text="Bootloader unlocked",
                text_color=COLORS["accent_green"],
            )
            self.bootloader_hint_label.configure(
                text="Bootloader is ready. You can start flashing now."
            )
            self._update_bootloader_ui(self.device_state, self.device_serial)
            return

        self.log_panel.append(f"Could not unlock bootloader: {detail or 'fastboot command failed'}")
        if parse_bootloader_unlock_status(detail) is True:
            self.unlock_status = True
            self.unlock_status_serial = serial
            self.unlock_status_mode = "fastboot"
            self._unlock_status_pending = False
            self._unlock_status_pending_key = None
            self._update_bootloader_ui(self.device_state, self.device_serial)
            show_info(
                self,
                "Bootloader already unlocked",
                "The device reports that its bootloader is already unlocked.\n\n"
                "You can start flashing now; the unlock command is not needed again.",
            )
            return

        show_error(
            self,
            "Unlock bootloader failed",
            "Could not run fastboot flashing unlock.\n\n"
            f"{detail or 'Make sure the device is in bootloader mode and authorized.'}",
        )
        self._update_bootloader_ui(self.device_state, self.device_serial)

    def _set_icon(self):
        """Set window icon from assets/icon.png."""
        import sys
        import tkinter as tk

        # Determine base path (PyInstaller bundle or dev)
        if getattr(sys, '_MEIPASS', None):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        icon_path = os.path.join(base, "assets", "icon.png")
        if os.path.isfile(icon_path):
            try:
                icon = tk.PhotoImage(file=icon_path)
                self.iconphoto(False, icon)
                self._icon_ref = icon  # Keep reference to prevent GC
            except Exception:
                pass  # Icon is optional, don't crash

    def _init_update_check(self):
        """Start a silent background check for software updates on launch."""
        self.latest_update_info = None
        self.update_check_done = False

        def run_silent():
            try:
                # Wait 2 seconds to prioritize main app loading
                import time
                time.sleep(2)
                info = check_for_updates(APP_VERSION)
                self.update_check_done = True
                if info and info.get("update_available"):
                    self.latest_update_info = info
                    self.after(0, self._notify_update_available)
            except Exception:
                pass

        threading.Thread(target=run_silent, daemon=True).start()

    def _notify_update_available(self):
        """Change the header button to indicate an update is ready."""
        if hasattr(self, "update_btn") and self.latest_update_info:
            tag = self.latest_update_info.get("latest_version", "")
            self.update_btn.configure(
                text=f"Update: {tag}",
                fg_color=COLORS["accent_green"],
                hover_color=COLORS["success_hover"],
                text_color=COLORS["on_accent"],
                font=FONTS["heading_sm"],
            )
            self.log_panel.append(
                f"🔔 Software update available: {tag}! Click the green update button in the header to install."
            )

    def _on_update_btn_clicked(self):
        """Handle manual update check click with visual loading spinner."""
        # Disable button to prevent double clicks
        self.update_btn.configure(state="disabled")

        # Show and start loading spinner
        self.update_spinner.pack(side="left", padx=(SPACING["sm"], 0))
        self.update_spinner.start()

        def run():
            try:
                info = check_for_updates(APP_VERSION)
                self.after(0, self._on_manual_check_finished, info, None)
            except Exception as e:
                self.after(0, self._on_manual_check_finished, None, str(e))

        threading.Thread(target=run, daemon=True).start()

    def _on_manual_check_finished(self, info: dict | None, error_msg: str | None = None):
        """Clean up manual check spinner and display result dialog."""
        # Stop and hide spinner
        self.update_spinner.stop()
        self.update_spinner.pack_forget()

        # Re-enable update button
        self.update_btn.configure(state="normal")

        if info is not None:
            if info.get("update_available"):
                self.latest_update_info = info
                self._notify_update_available()
            UpdateDialog(self, APP_VERSION, info)
        else:
            err = error_msg or "Failed to query release updates. Please check your internet connection."
            UpdateDialog(self, APP_VERSION, None, error_msg=err)

    def destroy(self):
        self._poll_running = False
        if self.worker and self.worker.is_alive():
            self.worker.stop()
        if hasattr(self, "_scroll_manager"):
            self._scroll_manager.destroy()
        super().destroy()
