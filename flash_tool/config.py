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

# G6-family partition patterns used for automatic image resolution.
IMAGE_PATTERNS = {
    "super": ["super.img"],
    "vbmeta": ["vbmeta.img"],
    "system": ["system.img"],
    "system_ext": ["system_ext.img", "system_ext-*.img", "system_ext*.img"],
    "product": ["product.img"],                              # base root only
    "product_region": ["product-*.img", "product*.img"],    # region subdirs
    "vbmeta_system": ["vbmeta_system.img", "vbmeta_system-*.img", "vbmeta_system*.img"],
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
      - "product_region" and "vbmeta_system":
        searched in subdirs only.
      - Everything else: root + subdirs.
    """
    ROOT_ONLY = {"product"}
    SUBDIR_ONLY = {"product_region", "vbmeta_system"}

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


def get_clean_env() -> dict[str, str]:
    """Get a copy of the environment with PyInstaller's library search path overrides removed or restored."""
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        if "LD_LIBRARY_PATH_ORIG" in env:
            env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
        else:
            env.pop("LD_LIBRARY_PATH", None)

        if "DYLD_LIBRARY_PATH_ORIG" in env:
            env["DYLD_LIBRARY_PATH"] = env["DYLD_LIBRARY_PATH_ORIG"]
        else:
            env.pop("DYLD_LIBRARY_PATH", None)
    return env


# ── App Info ────────────────────────────────────────────────────────────────
APP_NAME = "FlashTool"
APP_VERSION = "1.3.1"
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 750
