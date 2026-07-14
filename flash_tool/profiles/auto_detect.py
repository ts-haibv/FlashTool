"""Auto-detection heuristics for firmware flash device type (PS11 / E11 / E10)."""

import os
import glob

AUTO_DETECT_LABEL = "Firmware Flash (Auto)"

DEVICE_SIGNATURES = {
    "PS10": {
        "variant_dirs": ["MN3", "PDN3", "PEN3", "PHN3", "TAN3", "TDN3", "TEN3"],
        "file_patterns": ["system_ext-lockon.img"],
    },
    "PS11": {
        "variant_dirs": ["Kira", "MN4", "PDN4", "PEN4", "Kira/PHN4", "Kira/TAN4", "Kira/TEN4"],
        "file_patterns": ["system_ext-*.img"],
    },
    "E11": {
        "variant_dirs": ["MC6", "PDC6", "PEC6", "PHC6", "PKC6"],
        "file_patterns": ["vendor.img", "boot.img"],
    },
    "E10": {
        "variant_dirs": ["MC5", "PDC5", "PEC5", "PHC5", "PKC5", "TAC5", "TDC5", "TEC5"],
        "file_patterns": ["system_ext-lyle.img", "init_boot.img", "pvmfw.img"],
    },
}


def detect_device(rom_path: str) -> str | None:
    """Auto-detect device type from ROM folder contents.

    Returns 'PS11', 'E11', 'E10', or None if no match.

    Scoring:
      - Variant directory present: +10
      - Signature file matched:    +5
      - Best score >= 5 wins.
    """
    if not rom_path or not os.path.isdir(rom_path):
        return None

    scores: dict[str, int] = {}
    for device, sig in DEVICE_SIGNATURES.items():
        score = 0
        for vd in sig["variant_dirs"]:
            if os.path.isdir(os.path.join(rom_path, vd)):
                score += 10
        for pattern in sig["file_patterns"]:
            if glob.glob(os.path.join(rom_path, pattern)):
                score += 5
        scores[device] = score

    if not scores:
        return None

    best = max(scores, key=scores.get)
    if scores[best] >= 5:
        return best
    return None


def detect_variant(rom_path: str, device: str, script_profiles: dict) -> str | None:
    """Auto-detect variant from ROM folder for a given device.

    Args:
        rom_path: Path to ROM folder.
        device: Device name (PS11, E11, E10).
        script_profiles: SCRIPT_PROFILES dict from main_window.
    """
    if not rom_path or device not in script_profiles:
        return None

    config = script_profiles[device]

    # First: check which variant dirs exist
    for variant in config["variants"]:
        dir_name = config["variant_dirs"].get(variant)
        if dir_name and os.path.isdir(os.path.join(rom_path, dir_name)):
            return variant

    # Second: try to infer from system_ext filename
    for variant in config["variants"]:
        if glob.glob(os.path.join(rom_path, f"system_ext-{variant}*")):
            return variant
    for variant in config["variants"]:
        if glob.glob(os.path.join(rom_path, f"system_ext-{variant.lower()}*")):
            return variant

    return config["default_variant"]
