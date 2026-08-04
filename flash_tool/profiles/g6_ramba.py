"""Shared flash profile builder for G6, X6, and X5 devices."""

from flash_tool.flash_worker import FlashStep


def build_g6_ramba_steps(use_super: bool = False) -> list[FlashStep]:
    """Build the shared G6-family flash profile.

    Image placeholders (image_key) will be resolved against detected files
    at runtime. The image_arg_index indicates which arg[] element to replace.

    Args:
        use_super: When True, replaces individual system/product/system_ext
                   flashing with a single super.img flash.
    """
    steps = [
        # ── Step 1: Reboot to Bootloader ───────────────────────────────
        FlashStep(
            id=1,
            name="Reboot to Bootloader",
            command="adb",
            args=["reboot", "bootloader"],
            timeout=30,
        ),

        # ── Step 2: Wait for Fastboot (bootloader) ────────────────────
        FlashStep(
            id=2,
            name="Wait for Bootloader (Fastboot)",
            command="fastboot",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="fastboot",
            wait_timeout=120,
        ),

        # ── Step 3: Unlock Bootloader ──────────────────────────────────
        FlashStep(
            id=3,
            name="Unlock Bootloader",
            command="fastboot",
            args=["flashing", "unlock"],
            timeout=30,
            user_action="⚠️  Confirm unlock on device screen (Volume keys + Power)",
        ),

        # ── Step 4: Verify Unlock ──────────────────────────────────────
        FlashStep(
            id=4,
            name="Verify Unlock Status",
            command="fastboot",
            args=["getvar", "unlocked"],
            timeout=10,
        ),

        # ── Step 5: Flash vbmeta ───────────────────────────────────────
        FlashStep(
            id=5,
            name="Flash vbmeta (disable verification)",
            command="fastboot",
            args=["flash", "vbmeta", "--disable-verification", "PLACEHOLDER"],
            timeout=30,
            image_key="vbmeta",
            image_arg_index=3,
        ),

        # ── Step 6: Reboot ─────────────────────────────────────────────
        FlashStep(
            id=6,
            name="Reboot Device",
            command="fastboot",
            args=["reboot"],
            timeout=30,
        ),

        # ── Step 7: Wait for ADB ───────────────────────────────────────
        FlashStep(
            id=7,
            name="Wait for Device (ADB)",
            command="adb",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="adb",
            wait_timeout=180,
        ),

        # ── Step 8: Reboot to Fastboot ─────────────────────────────────
        FlashStep(
            id=8,
            name="Reboot to Fastboot Mode",
            command="adb",
            args=["reboot", "fastboot"],
            timeout=30,
        ),

        # ── Step 9: Wait for Fastboot ─────────────────────────────────
        FlashStep(
            id=9,
            name="Wait for Device (Fastboot)",
            command="fastboot",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="fastboot",
            wait_timeout=120,
        ),
    ]

    # ── Steps 10-12: Partition Flash Strategy ─────────────────────────────
    if use_super:
        # Flash the combined super partition image
        steps += [
            FlashStep(
                id=10,
                name="Flash super.img",
                command="fastboot",
                args=["flash", "super", "PLACEHOLDER"],
                timeout=900,
                image_key="super",
                image_arg_index=2,
            ),
        ]
    else:
        # Flash individual partition images
        steps += [
            # ── Step 10: Flash System ──────────────────────────────────────
            FlashStep(
                id=10,
                name="Flash system.img",
                command="fastboot",
                args=["flash", "system", "PLACEHOLDER"],
                timeout=600,
                image_key="system",
                image_arg_index=2,
            ),

            # ── Step 11: Flash Product ─────────────────────────────────────
            FlashStep(
                id=11,
                name="Flash product.img",
                command="fastboot",
                args=["flash", "product", "PLACEHOLDER"],
                timeout=600,
                image_key="product",
                image_arg_index=2,
            ),

            # ── Step 12: Flash system_ext ──────────────────────────────────
            FlashStep(
                id=12,
                name="Flash system_ext.img",
                command="fastboot",
                args=["flash", "system_ext", "PLACEHOLDER"],
                timeout=600,
                image_key="system_ext",
                image_arg_index=2,
            ),
        ]

    steps += [
        # ── Step 13: Erase Metadata ────────────────────────────────────
        FlashStep(
            id=13,
            name="Erase Metadata",
            command="fastboot",
            args=["erase", "metadata"],
            timeout=30,
        ),

        # ── Step 14: Erase Userdata ────────────────────────────────────
        FlashStep(
            id=14,
            name="Erase Userdata",
            command="fastboot",
            args=["erase", "userdata"],
            timeout=30,
        ),

        # ── Step 15: Final Reboot ──────────────────────────────────────
        FlashStep(
            id=15,
            name="Final Reboot",
            command="fastboot",
            args=["reboot"],
            timeout=30,
        ),
    ]
    return steps


def build_suw_only_steps() -> list[FlashStep]:
    """Build the standalone steps that bypass Android's Setup Wizard."""
    return [
        FlashStep(
            id=1,
            name="Wait for Device (ADB)",
            command="adb",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="adb",
            wait_timeout=60,
        ),
        FlashStep(
            id=2,
            name="SUW: Mark device_provisioned",
            command="adb",
            args=["shell", "settings", "put", "global", "device_provisioned", "1"],
            timeout=10,
        ),
        FlashStep(
            id=3,
            name="SUW: Mark user_setup_complete",
            command="adb",
            args=["shell", "settings", "put", "secure", "user_setup_complete", "1"],
            timeout=10,
        ),
        FlashStep(
            id=4,
            name="SUW: Mark setup_wizard_has_run",
            command="adb",
            args=["shell", "settings", "put", "secure", "setup_wizard_has_run", "1"],
            timeout=10,
        ),
        FlashStep(
            id=5,
            name="SUW: Reboot to apply provisioning",
            command="adb",
            args=["reboot"],
            timeout=30,
        ),
    ]
