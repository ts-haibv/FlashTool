"""Flash profile builder for Other Model devices."""

from flash_tool.flash_worker import FlashStep


def build_other_model_steps(skip_suw: bool = False) -> list[FlashStep]:
    """Build the flash profile for Other Model ROM following FLASH_STEPS.txt.

    Image placeholders (image_key) will be resolved against detected files
    at runtime. The image_arg_index indicates which arg[] element to replace.
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

        # ── Step 5: Flash boot ─────────────────────────────────────────
        FlashStep(
            id=5,
            name="Flash boot.img",
            command="fastboot",
            args=["flash", "boot", "PLACEHOLDER"],
            timeout=150,
            image_key="boot",
            image_arg_index=2,
        ),

        # ── Step 6: Flash dtbo ─────────────────────────────────────────
        FlashStep(
            id=6,
            name="Flash dtbo.img",
            command="fastboot",
            args=["flash", "dtbo", "PLACEHOLDER"],
            timeout=60,
            image_key="dtbo",
            image_arg_index=2,
        ),

        # ── Step 7: Flash init_boot ────────────────────────────────────
        FlashStep(
            id=7,
            name="Flash init_boot.img",
            command="fastboot",
            args=["flash", "init_boot", "PLACEHOLDER"],
            timeout=60,
            image_key="init_boot",
            image_arg_index=2,
        ),

        # ── Step 8: Flash vbmeta ───────────────────────────────────────
        FlashStep(
            id=8,
            name="Flash vbmeta.img",
            command="fastboot",
            args=["flash", "vbmeta", "PLACEHOLDER"],
            timeout=30,
            image_key="vbmeta",
            image_arg_index=2,
        ),

        # ── Step 9: Flash recovery ─────────────────────────────────────
        FlashStep(
            id=9,
            name="Flash recovery.img",
            command="fastboot",
            args=["flash", "recovery", "PLACEHOLDER"],
            timeout=150,
            image_key="recovery",
            image_arg_index=2,
        ),

        # ── Step 10: Reboot Fastbootd ──────────────────────────────────
        FlashStep(
            id=10,
            name="Reboot to Fastbootd",
            command="fastboot",
            args=["reboot", "fastboot"],
            timeout=30,
        ),

        # ── Step 11: Wait for Fastbootd ────────────────────────────────
        FlashStep(
            id=11,
            name="Wait for Device (Fastbootd)",
            command="fastboot",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="fastboot",
            wait_timeout=120,
        ),

        # ── Step 12: Flash system ──────────────────────────────────────
        FlashStep(
            id=12,
            name="Flash system.img",
            command="fastboot",
            args=["flash", "system", "PLACEHOLDER"],
            timeout=600,
            image_key="system",
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

        # ── Step 14: Flash vendor ──────────────────────────────────────
        FlashStep(
            id=14,
            name="Flash vendor.img",
            command="fastboot",
            args=["flash", "vendor", "PLACEHOLDER"],
            timeout=600,
            image_key="vendor",
            image_arg_index=2,
        ),

        # ── Step 15: Flash product ─────────────────────────────────────
        FlashStep(
            id=15,
            name="Flash product.img",
            command="fastboot",
            args=["flash", "product", "PLACEHOLDER"],
            timeout=600,
            image_key="product",
            image_arg_index=2,
        ),

        # ── Step 16: Flash regional product ────────────────────────────
        FlashStep(
            id=16,
            name="Flash product (Region)",
            command="fastboot",
            args=["flash", "product", "PLACEHOLDER"],
            timeout=600,
            image_key="product_region",
            image_arg_index=2,
        ),

        # ── Step 17: Flash regional userdata ───────────────────────────
        FlashStep(
            id=17,
            name="Flash userdata (Region)",
            command="fastboot",
            args=["flash", "userdata", "PLACEHOLDER"],
            timeout=300,
            image_key="userdata",
            image_arg_index=2,
        ),

        # ── Step 18: Flash regional vbmeta_system ──────────────────────
        FlashStep(
            id=18,
            name="Flash vbmeta_system (Region)",
            command="fastboot",
            args=["flash", "vbmeta_system", "PLACEHOLDER"],
            timeout=60,
            image_key="vbmeta_system",
            image_arg_index=2,
        ),

        # ── Step 19: Reboot Bootloader ─────────────────────────────────
        FlashStep(
            id=19,
            name="Reboot Bootloader",
            command="fastboot",
            args=["reboot", "bootloader"],
            timeout=30,
        ),

        # ── Step 20: Wait for Bootloader ───────────────────────────────
        FlashStep(
            id=20,
            name="Wait for Bootloader",
            command="fastboot",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="fastboot",
            wait_timeout=120,
        ),

        # ── Step 21: Flash modem ───────────────────────────────────────
        FlashStep(
            id=21,
            name="Flash modem (NON-HLOS.bin)",
            command="fastboot",
            args=["flash", "modem", "PLACEHOLDER"],
            timeout=150,
            image_key="modem",
            image_arg_index=2,
        ),

        # ── Step 22: Flash abl ─────────────────────────────────────────
        FlashStep(
            id=22,
            name="Flash abl.elf",
            command="fastboot",
            args=["flash", "abl", "PLACEHOLDER"],
            timeout=30,
            image_key="abl",
            image_arg_index=2,
        ),

        # ── Step 23: Flash tz ──────────────────────────────────────────
        FlashStep(
            id=23,
            name="Flash tz.mbn",
            command="fastboot",
            args=["flash", "tz", "PLACEHOLDER"],
            timeout=30,
            image_key="tz",
            image_arg_index=2,
        ),

        # ── Step 24: Erase Userdata ────────────────────────────────────
        FlashStep(
            id=24,
            name="Erase Userdata",
            command="fastboot",
            args=["erase", "userdata"],
            timeout=30,
        ),

        # ── Step 25: Final Reboot ──────────────────────────────────────
        FlashStep(
            id=25,
            name="Final Reboot",
            command="fastboot",
            args=["reboot"],
            timeout=30,
        ),
    ]

    # ── Optional: Skip Setup Wizard ────────────────────────────────────────
    if skip_suw:
        steps += [
            # ── Step 26: Wait for ADB after first boot ─────────────────
            FlashStep(
                id=26,
                name="Wait for Device (ADB) — Post-flash Boot",
                command="adb",
                args=["devices"],
                timeout=10,
                wait_for_device_mode="adb",
                wait_timeout=240,
            ),

            # ── Step 27: Mark device_provisioned ───────────────────────
            FlashStep(
                id=27,
                name="SUW: Mark device_provisioned",
                command="adb",
                args=["shell", "settings", "put", "global", "device_provisioned", "1"],
                timeout=10,
            ),

            # ── Step 28: Mark user_setup_complete ──────────────────────
            FlashStep(
                id=28,
                name="SUW: Mark user_setup_complete",
                command="adb",
                args=["shell", "settings", "put", "secure", "user_setup_complete", "1"],
                timeout=10,
            ),

            # ── Step 29: Mark setup_wizard_has_run ─────────────────────
            FlashStep(
                id=29,
                name="SUW: Mark setup_wizard_has_run",
                command="adb",
                args=["shell", "settings", "put", "secure", "setup_wizard_has_run", "1"],
                timeout=10,
            ),

            # ── Step 30: Final reboot to apply provisioning ─────────────
            FlashStep(
                id=30,
                name="SUW: Reboot to apply provisioning",
                command="adb",
                args=["reboot"],
                timeout=30,
            ),
        ]

    return steps
