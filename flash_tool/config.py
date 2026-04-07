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
    "vbmeta": ["vbmeta*.img"],
    "system": ["system.img"],
    "product": ["product*.img"],
    "system_ext": ["system_ext*.img"],
}


def scan_rom_folder(rom_path: str) -> dict[str, list[str]]:
    """Scan a ROM folder and auto-detect image files by partition type.

    Returns a dict like:
        {
          "vbmeta": ["EED3/vbmeta_system-eed3.img"],
          "system": ["system.img"],
          "product": ["EED3/product-eed3.img"],
          "system_ext": ["system_ext-ramba.img"],
        }
    """
    results: dict[str, list[str]] = {}

    for partition, patterns in IMAGE_PATTERNS.items():
        found: list[str] = []
        for pattern in patterns:
            # Search root and one level of subdirs
            found.extend(glob.glob(os.path.join(rom_path, pattern)))
            found.extend(glob.glob(os.path.join(rom_path, "**", pattern)))

        # De-duplicate and sort, store relative paths
        unique = sorted(set(found))
        results[partition] = [os.path.relpath(f, rom_path) for f in unique]

    return results


def get_file_size_mb(filepath: str) -> float:
    """Return file size in MB."""
    try:
        return os.path.getsize(filepath) / (1024 * 1024)
    except OSError:
        return 0.0


# ── App Info ────────────────────────────────────────────────────────────────
APP_NAME = "FlashTool"
APP_VERSION = "1.0.0"
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 750
