"""Flash profile builder for Other Model devices."""

from flash_tool.flash_worker import FlashStep


def build_other_model_steps(
    skip_suw: bool = False,
    use_fastbootd: bool = True,
    already_in_fastboot: bool = False,
    has_region: bool = False,
) -> list[FlashStep]:
    """Build the flash profile for Other Model ROM following FLASH_STEPS.txt.

    Args:
        skip_suw: Whether to skip Android Setup Wizard after first boot.
        use_fastbootd: If True, reboot to Fastbootd for dynamic partitions.
        already_in_fastboot: If True, skip the initial ADB reboot + wait steps.
        has_region: If True, skip the base product.img step (region variant handles it).

    Image placeholders (image_key) will be resolved against detected files
    at runtime. The image_arg_index indicates which arg[] element to replace.
    """
    steps = []
    step_id = 1

    # ── Step 1-2: Boot to Fastboot (skipped if already in fastboot mode) ──────
    if not already_in_fastboot:
        steps += [
            # Step 1: Reboot to Bootloader via ADB
            FlashStep(
                id=step_id,
                name="Reboot to Bootloader (ADB)",
                command="adb",
                args=["reboot", "bootloader"],
                timeout=30,
            ),
            # Step 2: Wait for Fastboot
            FlashStep(
                id=step_id + 1,
                name="Wait for Bootloader (Fastboot)",
                command="fastboot",
                args=["devices"],
                timeout=10,
                wait_for_device_mode="fastboot",
                wait_timeout=120,
            ),
        ]
        step_id += 2

    # ── Step: Check device in fastboot (always, to confirm) ────────────────────
    steps += [
        FlashStep(
            id=step_id,
            name="Check Device (Fastboot)",
            command="fastboot",
            args=["devices"],
            timeout=10,
            wait_for_device_mode="fastboot",
            wait_timeout=60,
        ),
    ]
    step_id += 1

    # ── Step: Unlock Bootloader ─────────────────────────────────────────────────
    steps += [
        FlashStep(
            id=step_id,
            name="Unlock Bootloader",
            command="fastboot",
            args=["flashing", "unlock"],
            timeout=60,
            user_action="⚠️  Confirm unlock on device screen (Volume keys + Power)",
        ),
    ]
    step_id += 1

    # ── Steps: Flash Core Partitions ────────────────────────────────────────────
    steps += [
        FlashStep(
            id=step_id,
            name="Flash boot.img",
            command="fastboot",
            args=["flash", "boot", "PLACEHOLDER"],
            timeout=150,
            image_key="boot",
            image_arg_index=2,
        ),
        FlashStep(
            id=step_id + 1,
            name="Flash dtbo.img",
            command="fastboot",
            args=["flash", "dtbo", "PLACEHOLDER"],
            timeout=60,
            image_key="dtbo",
            image_arg_index=2,
        ),
        FlashStep(
            id=step_id + 2,
            name="Flash init_boot.img",
            command="fastboot",
            args=["flash", "init_boot", "PLACEHOLDER"],
            timeout=60,
            image_key="init_boot",
            image_arg_index=2,
        ),
        FlashStep(
            id=step_id + 3,
            name="Flash vbmeta.img",
            command="fastboot",
            args=["flash", "vbmeta", "PLACEHOLDER"],
            timeout=30,
            image_key="vbmeta",
            image_arg_index=2,
        ),
        FlashStep(
            id=step_id + 4,
            name="Flash recovery.img",
            command="fastboot",
            args=["flash", "recovery", "PLACEHOLDER"],
            timeout=150,
            image_key="recovery",
            image_arg_index=2,
        ),
    ]
    step_id += 5

    # ── Steps: Fastbootd Transition (Conditional) ──────────────────────────────
    if use_fastbootd:
        steps += [
            FlashStep(
                id=step_id,
                name="Reboot to Fastbootd",
                command="fastboot",
                args=["reboot", "fastboot"],
                timeout=60,
            ),
            FlashStep(
                id=step_id + 1,
                name="Wait for Device (Fastbootd)",
                command="fastboot",
                args=["devices"],
                timeout=10,
                wait_for_device_mode="fastboot",
                wait_timeout=120,
            ),
        ]
        step_id += 2

    # ── Steps: Flash Dynamic / System Partitions ────────────────────────────────
    steps += [
        FlashStep(
            id=step_id,
            name="Flash system.img",
            command="fastboot",
            args=["flash", "system", "PLACEHOLDER"],
            timeout=600,
            image_key="system",
            image_arg_index=2,
        ),
        FlashStep(
            id=step_id + 1,
            name="Flash system_ext.img",
            command="fastboot",
            args=["flash", "system_ext", "PLACEHOLDER"],
            timeout=600,
            image_key="system_ext",
            image_arg_index=2,
        ),
        FlashStep(
            id=step_id + 2,
            name="Flash vendor.img",
            command="fastboot",
            args=["flash", "vendor", "PLACEHOLDER"],
            timeout=600,
            image_key="vendor",
            image_arg_index=2,
        ),
    ]
    step_id += 3

    # ── Step: Flash base product.img (ONLY when no region variant is selected) ──
    if not has_region:
        steps += [
            FlashStep(
                id=step_id,
                name="Flash product.img",
                command="fastboot",
                args=["flash", "product", "PLACEHOLDER"],
                timeout=600,
                image_key="product",
                image_arg_index=2,
            ),
        ]
        step_id += 1

    # ── Steps: Flash Regional Variant Files ────────────────────────────────────
    if has_region:
        steps += [
            FlashStep(
                id=step_id,
                name="Flash product (Region)",
                command="fastboot",
                args=["flash", "product", "PLACEHOLDER"],
                timeout=600,
                image_key="product_region",
                image_arg_index=2,
            ),
            FlashStep(
                id=step_id + 1,
                name="Flash userdata (Region)",
                command="fastboot",
                args=["flash", "userdata", "PLACEHOLDER"],
                timeout=300,
                image_key="userdata",
                image_arg_index=2,
            ),
            FlashStep(
                id=step_id + 2,
                name="Flash vbmeta_system (Region)",
                command="fastboot",
                args=["flash", "vbmeta_system", "PLACEHOLDER"],
                timeout=60,
                image_key="vbmeta_system",
                image_arg_index=2,
            ),
        ]
        step_id += 3

    # ── Steps: Return to Bootloader for Static Partitions ──────────────────────
    if use_fastbootd:
        steps += [
            FlashStep(
                id=step_id,
                name="Reboot Bootloader",
                command="fastboot",
                args=["reboot", "bootloader"],
                timeout=30,
            ),
            FlashStep(
                id=step_id + 1,
                name="Wait for Bootloader",
                command="fastboot",
                args=["devices"],
                timeout=10,
                wait_for_device_mode="fastboot",
                wait_timeout=120,
            ),
        ]
        step_id += 2

    # ── Steps: Flash Static Partitions (Modem, ABL, TZ) ────────────────────────
    steps += [
        FlashStep(
            id=step_id,
            name="Flash modem (NON-HLOS.bin)",
            command="fastboot",
            args=["flash", "modem", "PLACEHOLDER"],
            timeout=150,
            image_key="modem",
            image_arg_index=2,
        ),
        FlashStep(
            id=step_id + 1,
            name="Flash abl.elf",
            command="fastboot",
            args=["flash", "abl", "PLACEHOLDER"],
            timeout=30,
            image_key="abl",
            image_arg_index=2,
        ),
        FlashStep(
            id=step_id + 2,
            name="Flash tz.mbn",
            command="fastboot",
            args=["flash", "tz", "PLACEHOLDER"],
            timeout=30,
            image_key="tz",
            image_arg_index=2,
        ),
    ]
    step_id += 3

    # ── Steps: Erase + Final Reboot ─────────────────────────────────────────────
    steps += [
        FlashStep(
            id=step_id,
            name="Erase Userdata",
            command="fastboot",
            args=["erase", "userdata"],
            timeout=30,
        ),
        FlashStep(
            id=step_id + 1,
            name="Final Reboot",
            command="fastboot",
            args=["reboot"],
            timeout=30,
        ),
    ]
    step_id += 2

    # ── Optional: Skip Setup Wizard ─────────────────────────────────────────────
    if skip_suw:
        steps += [
            FlashStep(
                id=step_id,
                name="Wait for Device (ADB) — Post-flash Boot",
                command="adb",
                args=["devices"],
                timeout=10,
                wait_for_device_mode="adb",
                wait_timeout=240,
            ),
            FlashStep(
                id=step_id + 1,
                name="SUW: Mark device_provisioned",
                command="adb",
                args=["shell", "settings", "put", "global", "device_provisioned", "1"],
                timeout=10,
            ),
            FlashStep(
                id=step_id + 2,
                name="SUW: Mark user_setup_complete",
                command="adb",
                args=["shell", "settings", "put", "secure", "user_setup_complete", "1"],
                timeout=10,
            ),
            FlashStep(
                id=step_id + 3,
                name="SUW: Mark setup_wizard_has_run",
                command="adb",
                args=["shell", "settings", "put", "secure", "setup_wizard_has_run", "1"],
                timeout=10,
            ),
            FlashStep(
                id=step_id + 4,
                name="SUW: Reboot to apply provisioning",
                command="adb",
                args=["reboot"],
                timeout=30,
            ),
        ]

    return steps
