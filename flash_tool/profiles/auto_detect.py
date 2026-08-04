"""Auto-detection heuristics for G6-family and script-backed firmware."""

import os
import glob

AUTO_DETECT_LABEL = "Firmware Flash (Auto)"
G6_FAMILY_LABEL = "G6 / X6 / X5 / X5P"
G6_FAMILY_MODELS = frozenset({"G6", "X6", "X5", "X5P"})
G6_IMAGE_KEYS = ("super", "vbmeta", "system", "product", "system_ext")

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
    "E9": {
        "variant_dirs": ["MC4", "PDC4", "PEC4", "PHC4", "PKC4", "TAC4", "TDC4", "TEC4"],
        "file_patterns": ["system_ext-naze.img", "init_boot.img", "pvmfw.img"],
    },
}


def _pick_image(files: list[str], variant: str | None = None) -> str | None:
    """Pick a root image or the image from the requested variant directory."""
    if not files:
        return None
    if variant:
        variant_files = [
            path
            for path in files
            if os.path.dirname(os.path.normpath(path)) == variant
        ]
        if variant_files:
            return variant_files[0]

        root_files = [
            path for path in files
            if not os.path.dirname(os.path.normpath(path))
        ]
        return root_files[0] if root_files else None
    return files[0]


def get_g6_variants(detected_images: dict[str, list[str]]) -> list[str]:
    """Return variant directories containing regional G6-family images."""
    variants = {
        os.path.dirname(os.path.normpath(path))
        for key in ("product_region", "vbmeta_system")
        for path in detected_images.get(key, [])
        if os.path.dirname(os.path.normpath(path))
    }
    return sorted(variants)


def resolve_g6_images(
    detected_images: dict[str, list[str]],
    variant: str | None = None,
) -> dict[str, str]:
    """Choose G6-family images, optionally constrained to a variant directory."""
    selected = {}
    for key in G6_IMAGE_KEYS:
        image = _pick_image(detected_images.get(key, []), variant)
        if image:
            selected[key] = image

    # Regional ROM folders are valid fallbacks for these two partitions.
    if "product" not in selected:
        image = _pick_image(detected_images.get("product_region", []), variant)
        if image:
            selected["product"] = image
    if "vbmeta" not in selected:
        image = _pick_image(detected_images.get("vbmeta_system", []), variant)
        if image:
            selected["vbmeta"] = image
    return selected


def detect_device(rom_path: str) -> str | None:
    """Auto-detect device type from ROM folder contents.

    Returns a G6-family or script-backed device name, or None if no match.

    Scoring:
      - Variant directory present: +10
      - Signature file matched:    +5
      - Best score >= 5 wins.
    """
    if not rom_path or not os.path.isdir(rom_path):
        return None

    # These are unambiguous G6-family markers and must be checked before the
    # broad PS11 system_ext-*.img pattern.
    if glob.glob(os.path.join(rom_path, "system_ext-sx5p*.img")):
        return "X5P"
    if glob.glob(os.path.join(rom_path, "system_ext-sx5*.img")):
        return "X5"
    if (
        glob.glob(os.path.join(rom_path, "super.img"))
        or glob.glob(os.path.join(rom_path, "system_ext-ramba.img"))
    ):
        return "G6"

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

    # G6/RAMBA packages do not have a script-specific variant directory.
    # Recognize their documented partition layout only after script profiles
    # have had a chance to match, so system_ext-lockon remains PS10.
    has_system = bool(glob.glob(os.path.join(rom_path, "system.img")))
    has_system_ext = bool(glob.glob(os.path.join(rom_path, "system_ext*.img")))
    has_vbmeta = bool(glob.glob(os.path.join(rom_path, "vbmeta*.img")))
    has_g6_marker = has_system and has_system_ext and has_vbmeta
    if has_g6_marker:
        return "G6"
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
