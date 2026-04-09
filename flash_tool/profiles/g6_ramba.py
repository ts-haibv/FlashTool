"""Flash profile builder for G6 RAMBA device."""

from flash_tool.flash_worker import FlashStep


def build_g6_ramba_steps(skip_suw: bool = False, use_super: bool = False) -> list[FlashStep]:
    """Build the flash profile for G6 RAMBA ROM.

    Image placeholders (image_key) will be resolved against detected files
    at runtime. The image_arg_index indicates which arg[] element to replace.

    Args:
        skip_suw: When True, appends extra steps after the final reboot to
                  mark the device as already-provisioned, bypassing the
                  Android Setup Wizard (SUW) on first boot.
        use_super: When True, replaces individual system/product/system_ext
                   flashing (steps 11-13) with a single super.img flash.
    """
    steps = [
        # ── Step 1: Enable OEM Unlocking ───────────────────────────────
        FlashStep(
            id=1,
            name="Enable OEM Unlocking",
            command="adb",
            args=["shell", "settings", "put", "global", "oem_unlock_allowed", "1"],
            timeout=10,
            user_action=(
                "⚠️  If command fails, manually enable:\n"
                "Settings → Developer Options → OEM Unlocking → ON"
            ),
        ),

        # ── Step 2: Reboot to Bootloader ───────────────────────────────
        FlashStep(
            id=2,
            name="Reboot to Bootloader",
            command="adb",
            args=["reboot", "bootloader"],
            timeout=30,
        ),

        # ── Step 3: Wait for Fastboot (bootloader) ────────────────────
        FlashStep(
            id=3,
            name="Wait for Bootloader (Fastboot)",
            command="fastboot",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="fastboot",
            wait_timeout=120,
        ),

        # ── Step 4: Unlock Bootloader ──────────────────────────────────
        FlashStep(
            id=4,
            name="Unlock Bootloader",
            command="fastboot",
            args=["flashing", "unlock"],
            timeout=30,
            user_action="⚠️  Confirm unlock on device screen (Volume keys + Power)",
        ),

        # ── Step 5: Verify Unlock ──────────────────────────────────────
        FlashStep(
            id=5,
            name="Verify Unlock Status",
            command="fastboot",
            args=["getvar", "unlocked"],
            timeout=10,
        ),

        # ── Step 6: Flash vbmeta ───────────────────────────────────────
        FlashStep(
            id=6,
            name="Flash vbmeta (disable verification)",
            command="fastboot",
            args=["flash", "vbmeta", "--disable-verification", "PLACEHOLDER"],
            timeout=30,
            image_key="vbmeta",
            image_arg_index=3,
        ),

        # ── Step 7: Reboot ─────────────────────────────────────────────
        FlashStep(
            id=7,
            name="Reboot Device",
            command="fastboot",
            args=["reboot"],
            timeout=30,
        ),

        # ── Step 8: Wait for ADB ───────────────────────────────────────
        FlashStep(
            id=8,
            name="Wait for Device (ADB)",
            command="adb",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="adb",
            wait_timeout=180,
        ),

        # ── Step 9: Reboot to Fastboot ─────────────────────────────────
        FlashStep(
            id=9,
            name="Reboot to Fastboot Mode",
            command="adb",
            args=["reboot", "fastboot"],
            timeout=30,
        ),

        # ── Step 10: Wait for Fastboot ─────────────────────────────────
        FlashStep(
            id=10,
            name="Wait for Device (Fastboot)",
            command="fastboot",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="fastboot",
            wait_timeout=120,
        ),
    ]

    # ── Steps 11-13: Partition Flash Strategy ─────────────────────────────
    if use_super:
        # Flash the combined super partition image
        steps += [
            FlashStep(
                id=11,
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
            # ── Step 11: Flash System ──────────────────────────────────────
            FlashStep(
                id=11,
                name="Flash system.img",
                command="fastboot",
                args=["flash", "system", "PLACEHOLDER"],
                timeout=600,
                image_key="system",
                image_arg_index=2,
            ),

            # ── Step 12: Flash Product ─────────────────────────────────────
            FlashStep(
                id=12,
                name="Flash product.img",
                command="fastboot",
                args=["flash", "product", "PLACEHOLDER"],
                timeout=600,
                image_key="product",
                image_arg_index=2,
            ),

            # ── Step 13: Flash system_ext ──────────────────────────────────
            FlashStep(
                id=13,
                name="Flash system_ext.img",
                command="fastboot",
                args=["flash", "system_ext", "PLACEHOLDER"],
                timeout=600,
                image_key="system_ext",
                image_arg_index=2,
            ),
        ]

    steps += [
        # ── Step 14: Erase Metadata ────────────────────────────────────
        FlashStep(
            id=14,
            name="Erase Metadata",
            command="fastboot",
            args=["erase", "metadata"],
            timeout=30,
        ),

        # ── Step 15: Erase Userdata ────────────────────────────────────
        FlashStep(
            id=15,
            name="Erase Userdata",
            command="fastboot",
            args=["erase", "userdata"],
            timeout=30,
        ),

        # ── Step 16: Final Reboot ──────────────────────────────────────
        FlashStep(
            id=16,
            name="Final Reboot",
            command="fastboot",
            args=["reboot"],
            timeout=30,
        ),
    ]
    # ── Optional: Skip Setup Wizard ────────────────────────────────────────
    if skip_suw:
        steps += [
            # ── Step 17: Wait for ADB after first boot ─────────────────
            FlashStep(
                id=17,
                name="Wait for Device (ADB) — Post-flash Boot",
                command="adb",
                args=["devices"],
                timeout=10,
                wait_for_device_mode="adb",
                wait_timeout=240,
            ),

            # ── Step 18: Mark device_provisioned ───────────────────────
            FlashStep(
                id=18,
                name="SUW: Mark device_provisioned",
                command="adb",
                args=["shell", "settings", "put", "global", "device_provisioned", "1"],
                timeout=10,
            ),

            # ── Step 19: Mark user_setup_complete ──────────────────────
            FlashStep(
                id=19,
                name="SUW: Mark user_setup_complete",
                command="adb",
                args=["shell", "settings", "put", "secure", "user_setup_complete", "1"],
                timeout=10,
            ),

            # ── Step 20: Mark setup_wizard_has_run ─────────────────────
            FlashStep(
                id=20,
                name="SUW: Mark setup_wizard_has_run",
                command="adb",
                args=["shell", "settings", "put", "secure", "setup_wizard_has_run", "1"],
                timeout=10,
            ),

            # ── Step 21: Final reboot to apply provisioning ─────────────
            FlashStep(
                id=21,
                name="SUW: Reboot to apply provisioning",
                command="adb",
                args=["reboot"],
                timeout=30,
            ),
        ]

    return steps


def build_suw_only_steps() -> list[FlashStep]:
    """Build a standalone step list that only skips the Android Setup Wizard.

    Run this independently (no ROM required) when the device is already booted
    and connected via ADB. Executes the three provisioning settings puts then
    reboots so the changes take effect.
    """
    return [
        # ── Step 1: Wait for ADB ───────────────────────────────────────
        FlashStep(
            id=1,
            name="Wait for Device (ADB)",
            command="adb",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="adb",
            wait_timeout=60,
        ),

        # ── Step 2: Mark device_provisioned ───────────────────────────
        FlashStep(
            id=2,
            name="SUW: Mark device_provisioned",
            command="adb",
            args=["shell", "settings", "put", "global", "device_provisioned", "1"],
            timeout=10,
        ),

        # ── Step 3: Mark user_setup_complete ──────────────────────────
        FlashStep(
            id=3,
            name="SUW: Mark user_setup_complete",
            command="adb",
            args=["shell", "settings", "put", "secure", "user_setup_complete", "1"],
            timeout=10,
        ),

        # ── Step 4: Mark setup_wizard_has_run ─────────────────────────
        FlashStep(
            id=4,
            name="SUW: Mark setup_wizard_has_run",
            command="adb",
            args=["shell", "settings", "put", "secure", "setup_wizard_has_run", "1"],
            timeout=10,
        ),

        # ── Step 5: Reboot to apply provisioning ──────────────────────
        FlashStep(
            id=5,
            name="SUW: Reboot to apply provisioning",
            command="adb",
            args=["reboot"],
            timeout=30,
        ),
    ]
