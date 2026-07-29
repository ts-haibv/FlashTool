# FlashTool — Project Overview & PDR

## Purpose

FlashTool is a cross-platform desktop application for flashing ROM images onto Android devices. It automates the `adb`/`fastboot` command sequence required to unlock bootloaders, flash partition images, erase userdata, and reboot — all through a modern dark GUI instead of manual terminal commands.

## Target Users

| User Type | Context |
|-----------|---------|
| Internal QA / FW Engineers | Flashing daily or nightly ROM builds onto G6 (RAMBA) and partner devices |
| Field Technicians | Re-imaging devices in the field with minimal command-line exposure |
| Developers | Quick iteration on ROM builds with auto-detected image sets |

## Key Features

| Feature | Description |
|---------|-------------|
| Auto-detect ROM images | Scans a folder and matches partition images by glob patterns (`super`, `boot`, `system`, `product`, etc.) |
| Manual override | Browse and override any auto-detected image per partition |
| Real-time device polling | ADB/Fastboot status updated every 2 seconds |
| Per-step progress | Sparse-image upload progress parsed from fastboot output |
| Visual step tracker | Card-based step list with status icons, elapsed time, and progress bars |
| Skip SUW | Optional post-flash step to bypass Android Setup Wizard |
| Multi-device support | G6 RAMBA, generic "Other Model", PS11, E11, E10, E9 |
| Cross-platform | Windows and Ubuntu/Linux executables via PyInstaller |

## Supported Devices

| Model | Flash Method | Variants / Notes |
|-------|-------------|------------------|
| G6 (RAMBA) | Python profile (`g6_ramba.py`) | Step-by-step adb/fastboot; optional `super.img` or individual partitions |
| Other Model | Python profile (`other_model.py`) | Flexible partition flash; supports fastbootd, region variants |
| PS11 | Bash script (`flash_ps11.sh`) | Sharp Aquos KIRA; 4-phase flash with variants: `kira`, `mn4`, `pdn4`, `pen4` |
| E11 | Bash script (`flash_e11.sh`) | Auto-detects Official vs Jenkins ROM; variants: `MC6`, `PDC6`, `PEC6`, `PHC6`, `PKC6` |
| E10 | Bash script (`flash_e10.sh`) | Variants: `MC5`, `PDC5`, `PEC5`, `PHC5`, `PKC5`, `TAC5`, `TDC5`, `TEC5` |
| E9 | Bash script (`flash_e9.sh`) | Variants: `MC4`, `PDC4`, `PEC4`, `PHC4`, `PKC4`, `TAC4`, `TDC4`, `TEC4` (NAZE 17-OS) |

## Product Design Requirements (PDR)

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Detect adb/fastboot binaries on PATH or common install locations | P0 |
| FR-2 | Scan ROM folder and auto-detect partition images by pattern | P0 |
| FR-3 | Display real-time device state (adb / fastboot / disconnected) | P0 |
| FR-4 | Execute flash steps sequentially with timeout and cancel support | P0 |
| FR-5 | Parse sparse-image progress from fastboot stdout | P1 |
| FR-6 | Support post-flash "Skip SUW" provisioning via adb | P1 |
| FR-7 | Support script-backed profiles with visual phase decomposition | P1 |
| FR-8 | Build standalone executables for Windows and Linux | P1 |

### Constraints

| ID | Constraint |
|----|------------|
| C-1 | Requires `adb` and `fastboot` binaries installed separately; not bundled |
| C-2 | Bootloader unlock wipes all device data — irreversible |
| C-3 | Unlock step requires physical user interaction (Volume + Power) |
| C-4 | Some devices need fastbootd mode for dynamic partitions |
| C-5 | Script-backed profiles require `bash` (Linux) or WSL/Git Bash (Windows) |

### Success Criteria

| ID | Criteria |
|----|----------|
| SC-1 | A novice user can flash a G6 RAMBA ROM from folder selection to reboot in under 10 minutes |
| SC-2 | The app correctly auto-detects all standard partition images in 95%+ of ROM folder layouts |
| SC-3 | CI/CD produces working Linux and Windows binaries on every version tag |
| SC-4 | Flash process can be cancelled at any step without leaving the device in an unrecoverable state |

## Version

Current release: **v1.2.0**
