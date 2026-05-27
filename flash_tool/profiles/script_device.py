"""Flash profiles that delegate to device-specific shell scripts."""

from flash_tool.flash_worker import FlashStep


SCRIPT_TIMEOUT_SECONDS = 7200


def build_script_device_steps(
    device_name: str,
    script_name: str,
    script_args: list[str] | None = None,
) -> list[FlashStep]:
    """Build a single-step profile that runs a device flash script."""
    args = [script_name]
    if script_args:
        args.extend(script_args)
    args.append("-y")

    return [
        FlashStep(
            id=1,
            name=f"Run {device_name} flash script",
            command="script",
            args=args,
            timeout=SCRIPT_TIMEOUT_SECONDS,
        )
    ]
