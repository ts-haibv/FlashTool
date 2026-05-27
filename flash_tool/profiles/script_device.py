"""Flash profiles that delegate to device-specific shell scripts."""

from flash_tool.flash_worker import FlashStep


SCRIPT_TIMEOUT_SECONDS = 7200


def build_script_device_steps(device_name: str, script_name: str) -> list[FlashStep]:
    """Build a single-step profile that runs a device flash script."""
    return [
        FlashStep(
            id=1,
            name=f"Run {device_name} flash script",
            command="script",
            args=[script_name, "-y"],
            timeout=SCRIPT_TIMEOUT_SECONDS,
        )
    ]
