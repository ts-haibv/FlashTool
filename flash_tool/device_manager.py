"""ADB / Fastboot device detection and management."""

import subprocess
import time
from typing import Literal

from flash_tool.config import ADB_PATH, FASTBOOT_PATH

DeviceState = Literal["fastboot", "adb", "disconnected"]


def _run_cmd(args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return -1, "", f"Binary not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return -2, "", "Command timed out"


def detect_fastboot_device() -> str | None:
    """Return fastboot device serial or None."""
    code, stdout, _ = _run_cmd([FASTBOOT_PATH, "devices"])
    if code != 0:
        return None
    for line in stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in ("fastboot", "fastbootd"):
            return parts[0]
    return None


def detect_adb_device() -> str | None:
    """Return adb device serial or None."""
    code, stdout, _ = _run_cmd([ADB_PATH, "devices"])
    if code != 0:
        return None
    for line in stdout.strip().splitlines():
        if line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def get_device_state() -> tuple[DeviceState, str | None]:
    """Check device state. Returns (state, serial)."""
    serial = detect_fastboot_device()
    if serial:
        return "fastboot", serial

    serial = detect_adb_device()
    if serial:
        return "adb", serial

    return "disconnected", None


def wait_for_device(
    target_state: DeviceState,
    timeout: int = 120,
    poll_interval: float = 2.0,
    on_tick: callable = None,
) -> tuple[bool, str | None]:
    """Poll until device appears in the target state.

    Args:
        target_state: 'fastboot' or 'adb'
        timeout: Max seconds to wait
        poll_interval: Seconds between polls
        on_tick: Optional callback(elapsed_seconds)

    Returns:
        (success, serial)
    """
    start = time.time()
    while time.time() - start < timeout:
        state, serial = get_device_state()
        if state == target_state and serial:
            return True, serial

        if on_tick:
            on_tick(time.time() - start)

        time.sleep(poll_interval)

    return False, None


def get_unlock_status() -> bool | None:
    """Check if bootloader is unlocked. Returns None if can't determine."""
    code, stdout, _ = _run_cmd([FASTBOOT_PATH, "getvar", "unlocked"])
    # fastboot may output to stderr
    combined = stdout + _  # stderr was captured in _
    if "yes" in combined.lower():
        return True
    if "no" in combined.lower():
        return False
    return None
