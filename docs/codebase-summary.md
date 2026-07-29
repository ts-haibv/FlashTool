# FlashTool — Codebase Summary

## File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 26 | Entry point; sets customtkinter theme and launches `MainWindow` |
| `flash_tool/config.py` | 139 | Platform detection, binary path discovery, ROM folder scanning, app metadata |
| `flash_tool/updater.py` | 232 | App self-update manager: queries GitHub API, chunk download stream, hot swap executables |
| `flash_tool/device_manager.py` | 128 | ADB/Fastboot device detection, state polling, wait helpers, unlock check |
| `flash_tool/flash_worker.py` | 419 | Background thread worker: step execution, sparse progress parsing, script phase tracking |
| `flash_tool/ui/main_window.py` | 1399 | Main CTk window: header, sidebar, step list, log panel, footer, device polling |
| `flash_tool/ui/update_dialog.py` | 557 | Modern CTk software update dialog with download progress bars and restart buttons |
| `flash_tool/ui/step_widget.py` | 130 | Card widget per flash step (id, name, status, progress bar, elapsed time) |
| `flash_tool/ui/log_panel.py` | 80 | Scrollable console output textbox with auto-scroll and clear |
| `flash_tool/ui/theme.py` | 93 | Dark theme color palette, fonts, spacing constants, status config mapping |
| `flash_tool/profiles/g6_ramba.py` | 311 | G6 RAMBA profile builder: 16–18 step sequence |
| `flash_tool/profiles/other_model.py` | 344 | Generic device profile: flexible partitions, fastbootd, region variants |
| `flash_tool/profiles/script_device.py` | 88 | Script-backed profile builder (PS11, E11, E10, E9) with visual phase steps |
| `flash_ps11.sh` | 1246 | PS11 flashing script: 4-phase Qualcomm Snapdragon flash |
| `flash_e11.sh` | 504 | E11 flashing script: auto ROM detect, fastbootd support |
| `flash_e10.sh` | 537 | E10 flashing script: multi-variant support |
| `flash_e9.sh` | 545 | E9 flashing script: multi-variant support (MC4..TEC4, NAZE 17-OS) |
| `FlashTool.spec` | 83 | PyInstaller spec: includes assets, scripts, customtkinter data files |
| `.github/workflows/release.yml` | 165 | CI/CD: builds Linux + Windows binaries, .deb package, GitHub release |
| `scripts/build_linux.sh` | 144 | Local Linux build: PyInstaller + .deb packaging |
| `scripts/build_windows.bat` | 80 | Local Windows build: PyInstaller + Inno Setup script generation |
| `scripts/run_linux.sh` | 50 | Dev launcher for Linux (venv activate + python main.py) |
| `scripts/run_windows.bat` | 54 | Dev launcher for Windows (venv activate + python main.py) |
| `scripts/clean_checkerboard.py` | 51 | Asset processing utility |
| `scripts/process_icon.py` | 37 | Icon processing utility |
| `requirements.txt` | 1 | `customtkinter>=5.2.0` |

## Module Breakdown

### `flash_tool/` — Core Application Package

```
flash_tool/
├── __init__.py
├── config.py              # Platform utils, ROM scanning, app constants
├── updater.py             # Github Release API consumer, self-update installer
├── device_manager.py      # ADB/Fastboot device state machine
├── flash_worker.py        # Background thread executor
├── profiles/              # Flash step generators per device
│   ├── g6_ramba.py
│   ├── other_model.py
│   └── script_device.py
└── ui/                    # CustomTkinter widgets
    ├── main_window.py
    ├── update_dialog.py   # Software update dialog panel
    ├── step_widget.py
    ├── log_panel.py
    └── theme.py
```

### External Scripts (Root Level)

| Script | Device | Language | Key Behaviors |
|--------|--------|----------|---------------|
| `flash_ps11.sh` | PS11 (Sharp Aquos KIRA) | Bash | 4-phase: bootloader/firmware → non-slot → dynamic → userdata/finalize |
| `flash_e11.sh` | E11 | Bash | Auto Official/Jenkins detect; variants MC6/PDC6/PEC6/PHC6/PKC6; fastbootd; slot selection |
| `flash_e10.sh` | E10 | Bash | Multi-variant (MC5, PDC5, PEC5, PHC5, PKC5, TAC5, TDC5, TEC5) |
| `flash_e9.sh` | E9 | Bash | Multi-variant (MC4, PDC4, PEC4, PHC4, PKC4, TAC4, TDC4, TEC4, NAZE 17-OS) |

## Dependencies

| Dependency | Version | Role |
|------------|---------|------|
| Python | 3.10+ | Runtime |
| customtkinter | >=5.2.0 | Modern tkinter wrapper for dark-themed UI |
| PyInstaller | — | Standalone executable build |
| adb / fastboot | — | External Android platform tools (not bundled) |

## Architecture Patterns

| Pattern | Where Applied |
|---------|---------------|
| **Profile/Strategy** | `profiles/*.py` generate device-specific step lists; `MainWindow` switches profiles dynamically |
| **Background Worker** | `FlashWorker` extends `threading.Thread` to keep UI responsive during long-running fastboot commands |
| **Observer/Callback** | `FlashWorker` emits progress via `on_progress`, `on_log`, and `on_finished` callbacks |
| **Dataclass Configuration** | `FlashStep` and `FlashProgress` dataclasses define step schema and UI update payloads |
| **State Machine** | `StepStatus` enum drives step widget visuals: `pending → waiting → running → success/failed/skipped` |
| **Polling Loop** | `MainWindow._poll_device()` runs every 2s via `after()` to update device status indicator |
