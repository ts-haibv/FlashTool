"""Application configuration and platform utilities."""

import os
import sys
import shutil
import glob
import platform


# ── Platform Detection ──────────────────────────────────────────────────────
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
PLATFORM_NAME = "Windows" if IS_WINDOWS else "Linux"


# ── Binary Paths ────────────────────────────────────────────────────────────
def find_binary(name: str) -> str | None:
    """Find adb/fastboot binary in PATH or common locations."""
    found = shutil.which(name)
    if found:
        return found

    # Common install locations
    if IS_WINDOWS:
        search_dirs = [
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools"),
            r"C:\platform-tools",
            r"C:\Android\platform-tools",
        ]
    else:
        search_dirs = [
            "/usr/bin",
            "/usr/local/bin",
            os.path.expanduser("~/Android/Sdk/platform-tools"),
            os.path.expanduser("~/platform-tools"),
        ]

    for d in search_dirs:
        candidate = os.path.join(d, name + (".exe" if IS_WINDOWS else ""))
        if os.path.isfile(candidate):
            return candidate

    return None


ADB_PATH = find_binary("adb") or "adb"
FASTBOOT_PATH = find_binary("fastboot") or "fastboot"


# ── File Pattern Detection ──────────────────────────────────────────────────

# Mapping of partition name → glob pattern(s) to search for in ROM folder
IMAGE_PATTERNS = {
    "super": ["super.img"],
    "boot": ["boot.img"],
    "dtbo": ["dtbo.img"],
    "init_boot": ["init_boot.img"],
    "vbmeta": ["vbmeta.img"],
    "recovery": ["recovery.img", "recovery*.img"],
    "system": ["system.img"],
    "system_ext": ["system_ext.img", "system_ext-*.img", "system_ext*.img"],
    "vendor": ["vendor.img", "vendor-*.img"],
    "product": ["product.img"],                              # base root only
    "product_region": ["product-*.img", "product*.img"],    # region subdirs
    "userdata": ["userdata.img", "userdata-*.img", "userdata*.img"],
    "vbmeta_system": ["vbmeta_system.img", "vbmeta_system-*.img", "vbmeta_system*.img"],
    "modem": ["NON-HLOS.bin", "modem.img", "modem*.img"],
    "abl": ["abl.elf", "abl*.img"],
    "tz": ["tz.mbn", "tz*.img"],
}


def scan_rom_folder(rom_path: str) -> dict[str, list[str]]:
    """Scan a ROM folder and auto-detect image files by partition type.

    Returns a dict like:
        {
          "vbmeta": ["vbmeta.img"],
          "system_ext": ["system_ext-lockon.img"],
          "product_region": ["MN3/product-mn3.img"],
        }
    
    Rule:
      - "product" (base): only searched in the ROOT dir (no subdirs).
      - "product_region", "userdata", "vbmeta_system", "modem", "abl", "tz": 
        searched in subdirs only.
      - Everything else: root + subdirs.
    """
    ROOT_ONLY = {"product"}
    SUBDIR_ONLY = {"product_region", "userdata", "vbmeta_system", "modem", "abl", "tz"}

    results: dict[str, list[str]] = {}

    for partition, patterns in IMAGE_PATTERNS.items():
        found: list[str] = []
        for pattern in patterns:
            if partition in ROOT_ONLY:
                # Only search root level
                found.extend(glob.glob(os.path.join(rom_path, pattern)))
            elif partition in SUBDIR_ONLY:
                # Only search one level of subdirs
                found.extend(glob.glob(os.path.join(rom_path, "*", pattern)))
            else:
                # Search root + subdirs
                found.extend(glob.glob(os.path.join(rom_path, pattern)))
                found.extend(glob.glob(os.path.join(rom_path, "*", pattern)))

        # De-duplicate, sort, store relative paths
        unique = sorted(set(found))
        results[partition] = [os.path.relpath(f, rom_path) for f in unique]

    return results


def scan_regions(rom_path: str) -> list[str]:
    """Scan immediate subdirectories of a ROM folder to detect regions (e.g. MN3, PDN3)."""
    regions = []
    if not os.path.exists(rom_path):
        return regions
    for entry in os.listdir(rom_path):
        full_path = os.path.join(rom_path, entry)
        if os.path.isdir(full_path) and not entry.startswith("."):
            regions.append(entry)
    return sorted(regions)


def get_file_size_mb(filepath: str) -> float:
    """Return file size in MB."""
    try:
        return os.path.getsize(filepath) / (1024 * 1024)
    except OSError:
        return 0.0


# ── App Info ────────────────────────────────────────────────────────────────
APP_NAME = "FlashTool"
APP_VERSION = "1.1.8"
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 750
