"""Flash profiles that delegate to device-specific shell scripts."""

from flash_tool.flash_worker import FlashStep


SCRIPT_TIMEOUT_SECONDS = 7200

SCRIPT_PHASES = {
    "PS11": [
        ("Validate package and fastboot device", r"ENVIRONMENT VALIDATION|SHARP AQUOS KIRA"),
        ("Flash bootstrap partitions", r"PHASE: 1 — BOOTSTRAP|BOOTSTRAP"),
        ("Flash non-slot partitions", r"PHASE: 2 — NON-SLOT|NON-SLOT PARTITIONS"),
        ("Flash firmware partitions", r"PHASE: 3 — FIRMWARE|FIRMWARE PARTITIONS"),
        ("Flash dynamic partitions in fastbootd", r"PHASE: 4 — DYNAMIC|DYNAMIC PARTITIONS"),
        ("Wipe userdata and finalize", r"PHASE: 5 — USERDATA|USERDATA & FINALIZE"),
    ],
    "E11": [
        ("Validate package and enter bootloader", r"Reboot to bootloader|Device already in fastboot"),
        ("Flash fastbootd bootstrap partitions", r"Flash boot images needed for fastbootd"),
        ("Enter fastbootd and prepare super", r"Reboot to fastbootd|Prepare super partition"),
        ("Flash dynamic partitions", r"Flash dynamic partitions"),
        ("Wipe userdata", r"Wipe userdata"),
        ("Flash bootloader and physical partitions", r"Flash bootloader and boot-slot partitions"),
        ("Set active slot and reboot", r"Set active slot|Reboot device"),
    ],
    "E10": [
        ("Validate package and enter bootloader", r"Device already in fastboot|Reboot to bootloader"),
        ("Flash fastbootd bootstrap partitions", r"Flash boot images needed for fastbootd"),
        ("Enter fastbootd and flash dynamic partitions", r"Device already in fastbootd|Flash dynamic partitions"),
        ("Reboot to bootloader for firmware", r"Reboot to bootloader for firmware"),
        ("Flash bootloader and modem partitions", r"Flash bootloader partitions|Flash modem"),
        ("Flash vbmeta and physical partitions", r"Flash vbmeta|Flash non-slot physical"),
        ("Set active slot and reboot", r"Set active slot|Reboot device"),
    ],
}


def build_script_device_steps(
    device_name: str,
    script_name: str,
    script_args: list[str] | None = None,
) -> list[FlashStep]:
    """Build a script-backed profile with visual phase steps."""
    args = [script_name]
    if script_args:
        args.extend(script_args)
    args.append("-y")

    steps = [
        FlashStep(
            id=1,
            name=f"Run {device_name} flash script",
            command="script",
            args=args,
            timeout=SCRIPT_TIMEOUT_SECONDS,
        )
    ]

    for index, (name, pattern) in enumerate(SCRIPT_PHASES.get(device_name, []), start=2):
        steps.append(
            FlashStep(
                id=index,
                name=name,
                command="script_phase",
                args=[],
                script_phase_pattern=pattern,
            )
        )

    return steps
