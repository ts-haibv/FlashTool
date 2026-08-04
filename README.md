# ⚡ FlashTool — G6-family ROM Flash Tool

Cross-platform desktop application for flashing ROM images onto G6-family (G6, X6, X5, X5P) devices.
Supports **Windows** and **Ubuntu/Linux**.

---

## Features

- 🔍 **Auto-resolve ROM images** — selects the required G6-family images directly from the firmware folder
- 📡 **Device auto-detection** — real-time polling for ADB/Fastboot device status
- 🧭 **Bootloader actions** — reboot an authorized ADB device, check unlock status, and run the unlock command from separate buttons
- 🧰 **Skip Setup Wizard** — mark an ADB device as provisioned and reboot it from the footer action bar
- 🚀 **15-step G6-family flash process** — unlock → flash → erase → reboot
- 📊 **Real-time progress** — per-step progress bars with sparse-image tracking
- 📋 **Console output** — live command output log
- 🎨 **Modern dark UI** — built with CustomTkinter
- 🖱️ **Focused list scrolling** — mouse wheel follows the active configuration or flash-step list

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

### First-time bootloader setup

Before the first unlock, boot the phone into Android and connect it over USB. If Developer options is hidden, open **Settings → About phone** and tap **Build number** seven times. Then enable **USB debugging** and **OEM unlocking** in Developer options.

When ADB is connected, FlashTool reads `ro.boot.flash.locked` and `ro.boot.verifiedbootstate` to show whether the bootloader is already unlocked. Click **Reboot to bootloader** when ready. Fastboot status is checked again automatically; if it is locked, click **Run fastboot flashing unlock** and confirm the unlock on the device; if it is already unlocked, the app disables that action and tells you that you can continue flashing. The OEM toggle and final bootloader confirmation remain manual device actions by design; unlocking wipes user data.

After Android boots, the **Skip Setup Wizard** action in the footer can mark the device as provisioned through ADB and reboot it. Use it only when you intentionally want to bypass the first-run setup screens.

See the official Android guidance for [Developer options](https://developer.android.com/studio/debug/dev-options.html) and [bootloader unlocking](https://source.android.com/docs/core/architecture/bootloader/locking_unlocking).

---

## ROM Folder Structure

Place your G6/X6/X5/X5P ROM files in a folder with this layout:
```
BIN_RAMBA1_A4020Jenkins570_2020/
├── system.img
├── system_ext-ramba.img          (or system_ext*.img)
├── EED3/
│   ├── vbmeta_system-eed3.img   (or vbmeta*.img)
│   └── product-eed3.img         (or product*.img)
```

The app detects X5/X5P packages from `system_ext-sx5.img` and
`system_ext-sx5p.img`. If the ROM contains regional variant directories such as
`ML2`, select the desired variant in the **Variant** field; its matching
`product-*` and `vbmeta_system-*` images are then used for flashing.

Example X5P layout:
```
BIN_SECBOOT_SX5P_17_A7300_2026/
├── system.img
├── system_ext-sx5p.img
└── ML2/
    ├── product-ml2.img
    └── vbmeta_system-ml2.img
```

---

## Flash Steps (G6 / X6 / X5 / X5P)

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

Internal tool — G6-family device flashing support.
