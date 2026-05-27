"""Main application window — ties all components together."""

import os
import sys
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

from flash_tool.config import (
    APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT,
    PLATFORM_NAME, ADB_PATH, FASTBOOT_PATH,
    scan_rom_folder, scan_regions, get_file_size_mb,
)
from flash_tool.device_manager import get_device_state
from flash_tool.flash_worker import FlashWorker, FlashProgress, StepStatus
from flash_tool.profiles.g6_ramba import build_g6_ramba_steps, build_suw_only_steps
from flash_tool.profiles.other_model import build_other_model_steps
from flash_tool.profiles.script_device import build_script_device_steps
from flash_tool.ui.theme import COLORS, FONTS, SPACING
from flash_tool.ui.step_widget import StepWidget
from flash_tool.ui.log_panel import LogPanel


class MainWindow(ctk.CTk):
    """Main application window."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ── Window Setup ──
        self.title(f"{APP_NAME} v{APP_VERSION} — ROM Flash Tool")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(900, 600)
        self.configure(fg_color=COLORS["bg_primary"])

        # Set window icon
        self._set_icon()

        # State
        self.current_model = ctk.StringVar(value="G6")
        self.MODEL_PARTITIONS = {
            "G6": ["super", "vbmeta", "system", "product", "system_ext"],
            "Other Model": ["boot", "dtbo", "init_boot", "vbmeta", "recovery", "system", "system_ext", "vendor", "product", "product_region", "userdata", "vbmeta_system", "modem", "abl", "tz"],
            "PS11": [],
            "E11": [],
        }
        self.SCRIPT_PROFILES = {
            "PS11": {
                "script": "flash_ps11.sh",
                "variant_arg": "-v",
                "variants": ["kira", "mn4", "pdn4", "pen4"],
                "variant_dirs": {
                    "kira": "Kira",
                    "mn4": "MN4",
                    "pdn4": "PDN4",
                    "pen4": "PEN4",
                },
                "default_args": ["-w"],
                "default_variant": "kira",
            },
            "E11": {
                "script": "flash_e11.sh",
                "variant_arg": "-m",
                "variants": ["MC6", "PDC6", "PEC6"],
                "variant_dirs": {
                    "MC6": "MC6",
                    "PDC6": "PDC6",
                    "PEC6": "PEC6",
                },
                "default_args": ["--wipe"],
                "default_variant": "MC6",
            },
        }
        self.rom_path: str = ""
        self.detected_images: dict[str, list[str]] = {}
        self.selected_images: dict[str, str] = {}
        self.selected_script_variants: dict[str, str] = {
            model: config["default_variant"]
            for model, config in self.SCRIPT_PROFILES.items()
        }
        self.skip_suw_var = ctk.BooleanVar(value=False)
        self.use_super = False
        self.flash_steps = []
        self.worker: FlashWorker | None = None
        self.step_widgets: dict[int, StepWidget] = {}
        self.image_combos: dict[str, ctk.CTkComboBox] = {}

        # Device polling
        self._poll_running = True

        # Build UI — footer must be packed before body so that pack's expand
        # doesn't let the body claim all vertical space before the footer lands.
        self._build_header()
        self._build_footer()
        self._build_body()
        
        self._update_flash_steps()

        # Start device polling
        self._poll_device()

    # ════════════════════════════════════════════════════════════════════════
    # HEADER
    # ════════════════════════════════════════════════════════════════════════
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        # App title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=SPACING["lg"], pady=SPACING["sm"])

        ctk.CTkLabel(
            title_frame,
            text=f"⚡ {APP_NAME}",
            font=FONTS["heading_lg"],
            text_color=COLORS["accent_blue"],
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text=f"  v{APP_VERSION}  •  {PLATFORM_NAME}",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
        ).pack(side="left", padx=(SPACING["sm"], 0))

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
        sidebar = ctk.CTkFrame(parent, fg_color=COLORS["bg_secondary"], corner_radius=0, width=340)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # ── Model Selection Section ──
        section_model = ctk.CTkFrame(sidebar, fg_color="transparent")
        section_model.pack(fill="x", padx=SPACING["md"], pady=(SPACING["lg"], 0))

        ctk.CTkLabel(
            section_model,
            text="📱  Model Selection",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x")

        self.model_combo = ctk.CTkComboBox(
            section_model,
            values=["G6", "Other Model", "PS11", "E11"],
            variable=self.current_model,
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
            height=34,
            state="readonly",
            command=self._on_model_changed,
        )
        self.model_combo.pack(fill="x", pady=(SPACING["sm"], 0))

        # ── ROM Folder Section ──
        section_rom = ctk.CTkFrame(sidebar, fg_color="transparent")
        section_rom.pack(fill="x", padx=SPACING["md"], pady=(SPACING["lg"], SPACING["sm"]))

        ctk.CTkLabel(
            section_rom,
            text="📁  ROM Folder",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x")

        rom_row = ctk.CTkFrame(section_rom, fg_color="transparent")
        rom_row.pack(fill="x", pady=(SPACING["sm"], 0))

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

        browse_btn = ctk.CTkButton(
            rom_row,
            text="Browse",
            font=FONTS["body_sm"],
            width=70,
            height=34,
            fg_color=COLORS["accent_blue"],
            hover_color="#4a70d4",
            corner_radius=6,
            command=self._browse_rom,
        )
        browse_btn.pack(side="right")

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

        # ── Detected Images Section ──
        divider1 = ctk.CTkFrame(sidebar, fg_color=COLORS["border"], height=1)
        divider1.pack(fill="x", padx=SPACING["md"], pady=SPACING["md"])

        ctk.CTkLabel(
            sidebar,
            text="🔍  Detected Images",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=SPACING["md"])

        self.images_frame = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color=COLORS["scrollbar_fg"],
        )
        self.images_frame.pack(fill="both", expand=True, padx=SPACING["md"], pady=(SPACING["sm"], SPACING["md"]))

        self._build_image_selectors()

        # ── Options Section ──
        divider2 = ctk.CTkFrame(sidebar, fg_color=COLORS["border"], height=1)
        divider2.pack(fill="x", padx=SPACING["md"], pady=SPACING["md"])

        ctk.CTkLabel(
            sidebar,
            text="⚙️  Options",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=SPACING["md"])

        options_frame = ctk.CTkFrame(sidebar, fg_color=COLORS["bg_tertiary"], corner_radius=8)
        options_frame.pack(fill="x", padx=SPACING["md"], pady=(SPACING["sm"], 0))

        suw_row = ctk.CTkFrame(options_frame, fg_color="transparent")
        suw_row.pack(fill="x", padx=SPACING["sm"], pady=SPACING["sm"])

        self.suw_checkbox = ctk.CTkCheckBox(
            suw_row,
            text="Skip Setup Wizard (SUW)",
            font=FONTS["body_sm"],
            text_color=COLORS["text_primary"],
            fg_color=COLORS["accent_blue"],
            hover_color="#4a70d4",
            checkmark_color=COLORS["text_primary"],
            variable=self.skip_suw_var,
            command=self._on_suw_toggle,
        )
        self.suw_checkbox.pack(side="left")

        ctk.CTkLabel(
            options_frame,
            text="Marks device as provisioned via ADB\nafter first boot — bypasses Android SUW",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))

        # ── Flash Strategy Indicator ──
        self.strategy_frame = ctk.CTkFrame(sidebar, fg_color=COLORS["bg_tertiary"], corner_radius=8)
        self.strategy_frame.pack(fill="x", padx=SPACING["md"], pady=(SPACING["sm"], 0))

        ctk.CTkLabel(
            self.strategy_frame,
            text="⚡  Flash Strategy",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
        ).pack(fill="x", padx=SPACING["sm"], pady=(SPACING["sm"], 0))

        self.strategy_label = ctk.CTkLabel(
            self.strategy_frame,
            text="📦  system + product + system_ext",
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.strategy_label.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))
        
        self.use_fastbootd = ctk.BooleanVar(value=True)
        self.fastbootd_checkbox = ctk.CTkCheckBox(
            self.strategy_frame,
            text="Use Fastbootd (Dynamic Partitions)",
            variable=self.use_fastbootd,
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
            checkbox_width=18,
            checkbox_height=18,
            command=self._update_flash_steps
        )

        self.already_in_fastboot = ctk.BooleanVar(value=False)
        self.fastboot_already_checkbox = ctk.CTkCheckBox(
            self.strategy_frame,
            text="Device already in Fastboot mode",
            variable=self.already_in_fastboot,
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
            checkbox_width=18,
            checkbox_height=18,
            command=self._update_flash_steps
        )
        # Packed dynamically based on profile

        # ── Info Section ──
        divider3 = ctk.CTkFrame(sidebar, fg_color=COLORS["border"], height=1)
        divider3.pack(fill="x", padx=SPACING["md"], pady=SPACING["md"])

        info_frame = ctk.CTkFrame(sidebar, fg_color=COLORS["bg_tertiary"], corner_radius=8)
        info_frame.pack(fill="x", padx=SPACING["md"], pady=(0, SPACING["sm"]))

        ctk.CTkLabel(
            info_frame,
            text="ℹ️  Tool Paths",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
        ).pack(fill="x", padx=SPACING["sm"], pady=(SPACING["sm"], 0))

        ctk.CTkLabel(
            info_frame,
            text=f"adb: {ADB_PATH}",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
        ).pack(fill="x", padx=SPACING["sm"])

        ctk.CTkLabel(
            info_frame,
            text=f"fastboot: {FASTBOOT_PATH}",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
        ).pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))
        
    def _build_image_selectors(self):
        # Clear existing
        for widget in self.images_frame.winfo_children():
            widget.destroy()
        self.image_combos.clear()
        self.selected_images.clear()

        # Build image selectors for each partition
        partitions = self.MODEL_PARTITIONS[self.current_model.get()]

        for key in partitions:
            row = ctk.CTkFrame(self.images_frame, fg_color="transparent")
            row.pack(fill="x", pady=SPACING["xs"])

            ctk.CTkLabel(
                row,
                text=f"{key}:",
                font=FONTS["body_sm"],
                text_color=COLORS["text_secondary"],
                width=90,
                anchor="w",
            ).pack(side="left")

            combo = ctk.CTkComboBox(
                row,
                values=["— not detected —"],
                font=FONTS["caption"],
                dropdown_font=FONTS["caption"],
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
                command=lambda v, k=key: self._on_image_selected(k, v),
            )
            combo.pack(side="left", fill="x", expand=True, padx=(SPACING["xs"], 0))
            self.image_combos[key] = combo

            # Browse button for manual selection
            btn = ctk.CTkButton(
                row,
                text="📂",
                width=28,
                height=28,
                fg_color=COLORS["bg_tertiary"],
                hover_color=COLORS["bg_hover"],
                corner_radius=4,
                command=lambda k=key: self._browse_image(k),
            )
            btn.pack(side="right", padx=(SPACING["xs"], 0))

        if self.detected_images:
            self._update_image_combos()

    def _on_model_changed(self, choice: str):
        self._build_image_selectors()
        self._update_region_visibility()
        
        # Show strategy frame at all times to hold context-specific toggles/info
        self.strategy_frame.pack(fill="x", padx=SPACING["md"], pady=(SPACING["sm"], 0))
        
        if self.current_model.get() == "G6":
            self.suw_checkbox.configure(state="normal")
            self.fastbootd_checkbox.pack_forget()
            self.fastboot_already_checkbox.pack_forget()
            self.strategy_label.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))
            self._update_super_strategy()
        else:
            self.use_super = False
            self.fastbootd_checkbox.pack_forget()
            self.fastboot_already_checkbox.pack_forget()

            if self.current_model.get() in self.SCRIPT_PROFILES:
                self.suw_checkbox.configure(state="disabled")
                script_name = self.SCRIPT_PROFILES[self.current_model.get()]["script"]
                self.strategy_label.configure(
                    text=f"📜  {script_name}",
                    text_color=COLORS["text_secondary"],
                )
                self.strategy_label.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))
                self._configure_script_variant_selector()
            else:
                self.suw_checkbox.configure(state="normal")
                self.strategy_label.pack_forget()
                self.fastbootd_checkbox.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["xs"]))
                self.fastboot_already_checkbox.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))
            
            if self.current_model.get() == "Other Model" and hasattr(self, "detected_regions") and self.detected_regions:
                # Trigger variant update for Other Model
                self._on_region_selected(self.region_combo.get())
            
        self._update_flash_steps()
        self.log_panel.append(f"📱 Switched model profile to: {choice}")

    def _build_center(self, parent):
        center = ctk.CTkFrame(parent, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew")
        center.grid_rowconfigure(0, weight=1)
        center.grid_rowconfigure(1, weight=0, minsize=200)
        center.grid_columnconfigure(0, weight=1)

        # ── Steps Panel ──
        steps_panel = ctk.CTkFrame(center, fg_color="transparent")
        steps_panel.grid(row=0, column=0, sticky="nsew", padx=SPACING["md"], pady=(SPACING["md"], 0))

        ctk.CTkLabel(
            steps_panel,
            text="🚀  Flash Steps",
            font=FONTS["heading_md"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", pady=(0, SPACING["sm"]))

        self.steps_scroll = ctk.CTkScrollableFrame(
            steps_panel,
            fg_color="transparent",
            scrollbar_button_color=COLORS["scrollbar_fg"],
        )
        self.steps_scroll.pack(fill="both", expand=True)

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
        footer = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0)
        footer.pack(fill="x", side="bottom", ipady=SPACING["sm"])

        self.start_btn = ctk.CTkButton(
            footer,
            text="⚡  Start Flash",
            font=FONTS["heading_md"],
            fg_color=COLORS["accent_blue"],
            hover_color="#4a70d4",
            height=64,
            width=210,
            corner_radius=10,
            command=self._start_flash,
        )
        self.start_btn.pack(side="right", padx=SPACING["lg"])

        self.stop_btn = ctk.CTkButton(
            footer,
            text="⏹  Stop",
            font=FONTS["heading_md"],
            fg_color=COLORS["accent_red"],
            hover_color="#d44a4a",
            height=64,
            width=120,
            corner_radius=10,
            command=self._stop_flash,
        )
        # stop_btn is hidden on startup; shown only while flashing
        self._stop_btn_pack_opts = {"side": "right", "padx": (0, SPACING["sm"])}

        self.suw_btn = ctk.CTkButton(
            footer,
            text="🔓  Skip SUW",
            font=FONTS["heading_md"],
            fg_color=COLORS["accent_orange"],
            hover_color="#c47a1e",
            height=64,
            width=165,
            corner_radius=10,
            command=self._run_suw_only,
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
        path = filedialog.askdirectory(title="Select ROM Folder")
        if not path:
            return

        self.rom_entry.delete(0, "end")
        self.rom_entry.insert(0, path)
        self._scan_rom_path(path)
        
    def _scan_rom_path(self, path: str):
        """Perform the actual scan for images and variants given a path."""
        self.rom_path = path
        self._last_scanned_path = path

        # Scan for images
        self.detected_images = scan_rom_folder(path)
        
        # Scan for all subdirectories that contain actual flashing images
        regions = set()
        region_keys = ["product", "product_region", "userdata", "vbmeta_system", "modem", "abl", "tz"]
        for key in region_keys:
            for file_path in self.detected_images.get(key, []):
                parts = file_path.replace("\\", "/").split("/")
                if len(parts) > 1:
                    regions.add(parts[0])
                    
        self.detected_regions = sorted(list(regions))
        if self.current_model.get() == "Other Model":
            if self.detected_regions:
                self._set_variant_selector(["— none —"] + self.detected_regions, self.detected_regions[0])
            else:
                self._set_variant_selector(["— none —"], "— none —")
            
        self._update_region_visibility()

        self._update_image_combos()
        self.log_panel.append(f"📁 ROM folder: {path}")

        if self.detected_regions and self.current_model.get() == "Other Model":
            self._on_region_selected(self.detected_regions[0])

        for partition, files in self.detected_images.items():
            if files:
                self.log_panel.append(f"  ✅ {partition}: {', '.join(files)}")
            else:
                self.log_panel.append(f"  ⚠️  {partition}: not found")
        self._update_super_strategy()

    def _update_region_visibility(self):
        """Show or hide the region selection row based on model and regions."""
        current_model = self.current_model.get()
        if current_model in self.SCRIPT_PROFILES:
            self._configure_script_variant_selector()
        elif hasattr(self, "detected_regions") and self.detected_regions and current_model == "Other Model":
            self._set_variant_selector(["— none —"] + self.detected_regions, self.region_combo.get())
        else:
            self.region_row.pack_forget()

    def _set_variant_selector(self, values: list[str], selected: str):
        """Show the shared Variant row with the provided values."""
        selected_value = selected if selected in values else values[0]
        self.region_combo.configure(values=values)
        self.region_combo.set(selected_value)
        self.region_row.pack(fill="x", pady=(SPACING["sm"], 0))

    def _get_script_variant_options(self, current_model: str) -> list[str]:
        """Return script variants, preferring folders present in the selected ROM."""
        config = self.SCRIPT_PROFILES[current_model]
        if not self.rom_path:
            return config["variants"]

        detected = [
            variant
            for variant in config["variants"]
            if os.path.isdir(os.path.join(self.rom_path, config["variant_dirs"][variant]))
        ]
        return detected or config["variants"]

    def _configure_script_variant_selector(self):
        """Show fixed script variants for PS11/E11 profiles."""
        current_model = self.current_model.get()
        config = self.SCRIPT_PROFILES[current_model]
        values = self._get_script_variant_options(current_model)
        selected_variant = self.selected_script_variants.get(
            current_model,
            config["default_variant"],
        )

        if selected_variant not in values:
            selected_variant = config["default_variant"] if config["default_variant"] in values else values[0]
            self.selected_script_variants[current_model] = selected_variant

        self._set_variant_selector(values, selected_variant)

    def _on_region_selected(self, choice: str):
        """Update selected images based on region variant."""
        current_model = self.current_model.get()
        if current_model in self.SCRIPT_PROFILES:
            self.selected_script_variants[current_model] = choice
            self.log_panel.append(f"🌍 Selected Variant: {choice}")
            self._update_flash_steps()
            return

        if choice == "— none —":
            return
        
        self.log_panel.append(f"🌍 Selected Variant: {choice}")
        
        region_keys = ["product", "product_region", "userdata", "vbmeta_system", "modem", "abl", "tz"]
        for key in region_keys:
            combo = self.image_combos.get(key)
            if not combo:
                continue
            
            values = combo.cget("values")
            for val in values:
                parts = val.replace("\\", "/").split("/")
                if len(parts) > 1 and parts[0] == choice:
                    combo.set(val)
                    self.selected_images[key] = val
                    break

    def _update_image_combos(self):
        """Update combo boxes with detected images."""
        for key, combo in self.image_combos.items():
            files = self.detected_images.get(key, [])
            
            # Fallback for G6 to catch regional images if base is missing
            if not files and self.current_model.get() == "G6":
                if key == "product":
                    files = self.detected_images.get("product_region", [])
                elif key == "vbmeta":
                    files = self.detected_images.get("vbmeta_system", [])

            if files:
                combo.configure(values=files)
                combo.set(files[0])  # Auto-select first match
                self.selected_images[key] = files[0]
            else:
                combo.configure(values=["— not detected —"])
                combo.set("— not detected —")
                self.selected_images.pop(key, None)

    def _on_image_selected(self, key: str, value: str):
        """Handle image combo selection."""
        if value != "— not detected —":
            self.selected_images[key] = value
        else:
            self.selected_images.pop(key, None)
        if key == "super":
            self._update_super_strategy()

    def _browse_image(self, key: str):
        """Manual image file selection."""
        filetypes = [("Image files", "*.img"), ("All files", "*.*")]
        path = filedialog.askopenfilename(
            title=f"Select {key} image",
            filetypes=filetypes,
            initialdir=self.rom_path or None,
        )
        if not path:
            return

        # Convert to relative path if within ROM folder
        if self.rom_path and path.startswith(self.rom_path):
            rel = os.path.relpath(path, self.rom_path)
        else:
            rel = path

        combo = self.image_combos[key]
        current_values = list(combo.cget("values") or [])
        if rel not in current_values:
            current_values.append(rel)
        combo.configure(values=current_values)
        combo.set(rel)
        self.selected_images[key] = rel
        self.log_panel.append(f"📂 Manual selection: {key} = {rel}")
        if key == "super":
            self._update_super_strategy()

    def _start_flash(self):
        """Validate and start the flash process."""
        # Validate ROM folder
        if not self.rom_path or not os.path.isdir(self.rom_path):
            messagebox.showerror("Error", "Please select a valid ROM folder first.")
            return

        # Validate required images based on flash strategy
        current_model = self.current_model.get()

        if current_model == "G6":
            if self.use_super:
                required = ["super"]
                optional_with_steps = ["vbmeta"]
            else:
                required = ["system"]  # system.img is always required
                optional_with_steps = ["vbmeta", "product", "system_ext"]
        elif current_model == "Other Model":
            required = ["boot", "system", "vendor"]
            optional_with_steps = ["dtbo", "init_boot", "vbmeta", "recovery", "system_ext", "product", "product_region", "userdata", "vbmeta_system", "modem", "abl", "tz"]
        else:
            required = []
            optional_with_steps = []
            script_name = self.SCRIPT_PROFILES[current_model]["script"]
            app_root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            script_candidates = [
                os.path.join(self.rom_path, script_name),
                os.path.join(app_root, script_name),
            ]
            if not any(os.path.isfile(path) for path in script_candidates):
                messagebox.showerror("Error", f"Flash script not found: {script_name}")
                return

        for key in required:
            if key not in self.selected_images:
                messagebox.showerror("Error", f"Required image not found: {key}\nPlease select it manually.")
                return

        # Warn about missing optional images
        missing_optional = [k for k in optional_with_steps if k not in self.selected_images]
        if missing_optional:
            msg = f"The following images were not detected:\n{', '.join(missing_optional)}\n\nSteps using these images will fail.\nContinue anyway?"
            if not messagebox.askyesno("Warning", msg):
                return

        # Confirm
        total_size = 0
        for key, img in self.selected_images.items():
            full_path = os.path.join(self.rom_path, img)
            total_size += get_file_size_mb(full_path)

        if current_model in self.SCRIPT_PROFILES:
            selected_variant = self.selected_script_variants[current_model]
            msg = (
                f"Ready to flash {current_model} device.\n\n"
                f"Firmware folder: {self.rom_path}\n"
                f"Script: {self.SCRIPT_PROFILES[current_model]['script']}\n"
                f"Variant: {selected_variant}\n\n"
                f"⚠️  This will ERASE all data on the device!\n\n"
                f"Continue?"
            )
        else:
            msg = (
                f"Ready to flash {current_model} device.\n\n"
                f"ROM: {self.rom_path}\n"
                f"Images: {len(self.selected_images)} selected ({total_size:.0f} MB total)\n\n"
                f"⚠️  This will ERASE all data on the device!\n\n"
                f"Continue?"
            )
        if not messagebox.askyesno("Confirm Flash", msg):
            return

        # Reset step widgets
        for w in self.step_widgets.values():
            w.update_status("pending")

        # Start total timer
        import time as _time
        self._flash_start_time = _time.time()
        self._tick_total_timer()

        # Update UI state — swap Start → Stop
        self.start_btn.pack_forget()
        self.stop_btn.pack(**self._stop_btn_pack_opts)
        self.suw_btn.configure(state="disabled")
        self.suw_checkbox.configure(state="disabled")
        self.model_combo.configure(state="disabled")
        self.status_label.configure(
            text="⚡ Flashing in progress...",
            text_color=COLORS["accent_orange"],
        )
        self.total_timer_label.configure(text="⏱ 0:00", text_color=COLORS["text_muted"])

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
            if messagebox.askyesno("Confirm", "Stop flashing? This may leave your device in an unstable state."):
                self.worker.stop()

    def _tick_total_timer(self):
        """Tick the total elapsed timer every second while flashing."""
        import time as _time
        if self._flash_start_time is None:
            return
        elapsed = _time.time() - self._flash_start_time
        minutes = int(elapsed) // 60
        seconds = int(elapsed) % 60
        self.total_timer_label.configure(text=f"⏱ {minutes}:{seconds:02d}")
        self._total_timer_id = self.after(1000, self._tick_total_timer)

    def _update_flash_steps(self):
        """Update steps based on selected model and strategy."""
        current_model = self.current_model.get()

        if current_model == "G6":
            self.flash_steps = build_g6_ramba_steps(skip_suw=self.skip_suw_var.get(), use_super=self.use_super)
        elif current_model == "Other Model":
            region = self.region_combo.get() if hasattr(self, "region_combo") else ""
            has_region = bool(region and region != "— none —")
            self.flash_steps = build_other_model_steps(
                skip_suw=self.skip_suw_var.get(),
                use_fastbootd=getattr(self, "use_fastbootd", ctk.BooleanVar(value=True)).get(),
                already_in_fastboot=getattr(self, "already_in_fastboot", ctk.BooleanVar(value=False)).get(),
                has_region=has_region,
            )
        else:
            config = self.SCRIPT_PROFILES[current_model]
            selected_variant = self.selected_script_variants[current_model]
            script_args = [config["variant_arg"], selected_variant] + config["default_args"]
            self.flash_steps = build_script_device_steps(
                current_model,
                config["script"],
                script_args,
            )
        self._rebuild_step_widgets()

    def _on_suw_toggle(self):
        """Rebuild step list when the Skip Setup Wizard checkbox is toggled."""
        self._update_flash_steps()

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
        if self.current_model.get() != "G6":
            return

        super_combo = self.image_combos.get("super")
        new_use_super = (
            super_combo is not None
            and super_combo.get() != "— not detected —"
        )
        strategy_changed = new_use_super != self.use_super
        self.use_super = new_use_super
        self._update_flash_steps()
        if self.use_super:
            self.strategy_label.configure(
                text="⚡  super.img (combined partition)",
                text_color=COLORS["accent_green"],
            )
            if strategy_changed:
                self.log_panel.append("⚡ super.img detected — switching to super flash strategy")
        else:
            self.strategy_label.configure(
                text="📦  system + product + system_ext",
                text_color=COLORS["text_secondary"],
            )
            if strategy_changed:
                self.log_panel.append("📦 super.img deselected — reverting to individual partition strategy")

    def _run_suw_only(self):
        """Run the Skip Setup Wizard steps standalone — no ROM folder needed."""
        if not messagebox.askyesno(
            "Skip Setup Wizard",
            "This will mark the connected ADB device as already provisioned\n"
            "and reboot it, skipping the Android Setup Wizard on next boot.\n\n"
            "Make sure the device is connected via ADB and the screen is on.\n\n"
            "Continue?",
        ):
            return

        # Swap step panel to show SUW-only steps
        suw_steps = build_suw_only_steps()
        for w in self.step_widgets.values():
            w.destroy()
        self.step_widgets.clear()
        for step in suw_steps:
            w = StepWidget(self.steps_scroll, step.id, step.name)
            w.pack(fill="x", pady=2)
            self.step_widgets[step.id] = w

        # Lock UI — swap Start → Stop
        self.start_btn.pack_forget()
        self.stop_btn.pack(**self._stop_btn_pack_opts)
        self.suw_btn.configure(state="disabled")
        self.suw_checkbox.configure(state="disabled")
        self.model_combo.configure(state="disabled")
        self.status_label.configure(
            text="🔓 Skipping Setup Wizard...",
            text_color=COLORS["accent_orange"],
        )

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
        """Handle SUW-only run completion (called from background thread)."""
        self.after(0, self._finish_suw, success)

    def _finish_suw(self, success: bool):
        """Restore UI after SUW-only run, then rebuild normal step list."""
        self.stop_btn.pack_forget()
        self.start_btn.pack(side="right", padx=SPACING["lg"])
        self.suw_btn.configure(state="normal")
        if self.current_model.get() in self.SCRIPT_PROFILES:
            self.suw_checkbox.configure(state="disabled")
        else:
            self.suw_checkbox.configure(state="normal")
        self.model_combo.configure(state="readonly")

        # Restore flash step widgets
        self._rebuild_step_widgets()

        if success:
            self.status_label.configure(
                text="✅ Setup Wizard skipped — device is rebooting",
                text_color=COLORS["accent_green"],
            )
            messagebox.showinfo("Done", "Setup Wizard skipped!\nDevice is rebooting.")
        else:
            self.status_label.configure(
                text="❌ SUW skip failed or stopped",
                text_color=COLORS["accent_red"],
            )

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

        self.stop_btn.pack_forget()
        self.start_btn.pack(side="right", padx=SPACING["lg"])
        self.suw_btn.configure(state="normal")
        if self.current_model.get() in self.SCRIPT_PROFILES:
            self.suw_checkbox.configure(state="disabled")
        else:
            self.suw_checkbox.configure(state="normal")
        self.model_combo.configure(state="readonly")

        if success:
            self.status_label.configure(
                text="✅ Flash completed successfully!",
                text_color=COLORS["accent_green"],
            )
            self.total_timer_label.configure(
                text=f"⏱ Total: {total_str}",
                text_color=COLORS["accent_green"],
            )
            messagebox.showinfo("Success", f"ROM flashed successfully!\nTotal time: {total_str}\nDevice is rebooting.")
        else:
            self.status_label.configure(
                text="❌ Flash failed or stopped",
                text_color=COLORS["accent_red"],
            )
            self.total_timer_label.configure(
                text=f"⏱ Stopped at: {total_str}",
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
            state, serial = get_device_state()
            self.after(0, self._update_device_ui, state, serial)

        threading.Thread(target=check, daemon=True).start()
        self.after(3000, self._poll_device)

    def _update_device_ui(self, state: str, serial: str | None):
        """Update device status display."""
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

    def destroy(self):
        self._poll_running = False
        if self.worker and self.worker.is_alive():
            self.worker.stop()
        super().destroy()
