# ⚡ FlashTool — G6 ROM Flash Tool

Cross-platform desktop application for flashing ROM images onto G6 (RAMBA) devices.  
Supports **Windows** and **Ubuntu/Linux**.

---

## Features

- 🔍 **Auto-detect ROM images** — scans folder for `vbmeta*.img`, `system.img`, `product*.img`, `system_ext*.img`
- 📂 **Manual file selection** — override any auto-detected image with manual browse
- 📡 **Device auto-detection** — real-time polling for ADB/Fastboot device status
- 🚀 **13-step flash process** — unlock → flash → erase → reboot
- 📊 **Real-time progress** — per-step progress bars with sparse-image tracking
- 📋 **Console output** — live command output log
- 🎨 **Modern dark UI** — built with CustomTkinter

---

## Requirements

| Requirement | Ubuntu | Windows |
|---|---|---|
| Python 3.10+ | `sudo apt install python3 python3-pip python3-tk` | [python.org](https://python.org) |
| adb & fastboot | `sudo apt install android-tools-adb android-tools-fastboot` | [platform-tools](https://developer.android.com/tools/releases/platform-tools) |

---

## Quick Start

### Ubuntu / Linux
```bash
chmod +x scripts/run_linux.sh
./scripts/run_linux.sh
```

### Windows
```cmd
scripts\run_windows.bat
```

### Manual
```bash
pip install -r requirements.txt
python main.py
```

---

## ROM Folder Structure

Place your ROM files in a folder with this layout:
```
BIN_RAMBA1_A4020Jenkins570_2020/
├── system.img
├── system_ext-ramba.img          (or system_ext*.img)
├── EED3/
│   ├── vbmeta_system-eed3.img   (or vbmeta*.img)
│   └── product-eed3.img         (or product*.img)
```

The app auto-detects images by pattern. If multiple matches exist, you can pick from the dropdown or browse manually.

---

## Flash Steps (G6 RAMBA)

| # | Step | Command |
|---|------|---------|
| 1 | Unlock Bootloader | `fastboot flashing unlock` |
| 2 | Verify Unlock | `fastboot getvar unlocked` |
| 3 | Flash vbmeta | `fastboot flash vbmeta --disable-verification <vbmeta*.img>` |
| 4 | Reboot | `fastboot reboot` |
| 5 | Wait for ADB | poll `adb devices` |
| 6 | Reboot to Fastboot | `adb reboot fastboot` |
| 7 | Wait for Fastboot | poll `fastboot devices` |
| 8 | Flash system | `fastboot flash system <system.img>` |
| 9 | Flash product | `fastboot flash product <product*.img>` |
| 10 | Flash system_ext | `fastboot flash system_ext <system_ext*.img>` |
| 11 | Erase metadata | `fastboot erase metadata` |
| 12 | Erase userdata | `fastboot erase userdata` |
| 13 | Final reboot | `fastboot reboot` |

---

## CI/CD Pipeline (Releases)

This project uses [GitHub Actions](.github/workflows/release.yml) to automatically build standalone executables for Linux (`FlashTool-Linux`) and Windows (`FlashTool-Windows.exe`) when a release tag is pushed.

### Triggering a New Release

1. Verify that your newest changes are pushed to the target branch (e.g., `main`).
2. Create and push a new Git tag following semantic versioning (it must start with `v`, e.g., `v1.0.0`):
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. A GitHub Action workflow named **Build Release** will start running.
4. Once completed, navigate to the **Releases** page in your GitHub repository. The compiled binaries will be immediately available to download.

*Alternatively, you can manually test compilation without making a final release by manually triggering the **Build Release** task from the GitHub **Actions** tab.*

---

## License

Internal tool — G6 device flashing support.
