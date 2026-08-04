"""ADB / Fastboot device detection and management."""

import re
import subprocess
import time
from typing import Literal

from flash_tool.config import ADB_PATH, FASTBOOT_PATH, get_clean_env

DeviceState = Literal["fastboot", "adb", "disconnected"]


def _device_command(binary: str, serial: str | None, args: list[str]) -> list[str]:
    """Build a command targeted at one device when a serial is available."""
    command = [binary]
    if serial:
        command.extend(["-s", serial])
    command.extend(args)
    return command


def _run_cmd(args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=get_clean_env(),
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


def wait_for_reboot(
    target_state: DeviceState,
    timeout: int = 120,
    poll_interval: float = 2.0,
    on_tick: callable = None,
) -> tuple[bool, str | None]:
    """Wait for device to disappear then reappear in target state.

    Useful for commands that trigger a device reboot (like unlock).
    """
    # 1. Wait for it to disappear (max 15s)
    start = time.time()
    while time.time() - start < 15:
        state, _ = get_device_state()
        if state == "disconnected":
            break
        time.sleep(1)

    # 2. Now wait for it to come back
    return wait_for_device(target_state, timeout, poll_interval, on_tick)


def reboot_to_bootloader(serial: str) -> tuple[bool, str]:
    """Reboot an authorized ADB device into the bootloader."""
    code, stdout, stderr = _run_cmd(
        _device_command(ADB_PATH, serial, ["reboot", "bootloader"])
    )
    detail = (stdout or stderr).strip()
    return code == 0, detail


def unlock_bootloader(serial: str) -> tuple[bool, str]:
    """Run the fastboot bootloader unlock command for one device."""
    code, stdout, stderr = _run_cmd(
        _device_command(FASTBOOT_PATH, serial, ["flashing", "unlock"]),
        timeout=120,
    )
    detail = "\n".join(part.strip() for part in (stdout, stderr) if part and part.strip())
    return code == 0, detail


def parse_bootloader_unlock_status(output: str) -> bool | None:
    """Parse fastboot output and return unlocked, locked, or unknown."""
    normalized = output.lower()

    if re.search(r"\bnot\s+unlocked\b", normalized):
        return False
    match = re.search(
        r"\bunlocked\s*[:=]\s*(yes|no|true|false|1|0)\b",
        normalized,
    )
    if match:
        return match.group(1) in {"yes", "true", "1"}
    if re.search(r"\balready\b[^\n]*\bunlocked\b", normalized):
        return True
    return None


def parse_adb_bootloader_unlock_status(
    flash_locked: str,
    verified_boot_state: str,
) -> bool | None:
    """Parse Android boot properties into a bootloader unlock state."""
    locked_value = flash_locked.strip().lower()
    verified_value = verified_boot_state.strip().lower()

    if locked_value in {"0", "no", "false", "unlocked"}:
        return True
    if locked_value in {"1", "yes", "true", "locked"}:
        return False

    # AVB reports orange when the bootloader is unlocked. Green/yellow means
    # the device is operating with a locked verified-boot chain.
    if verified_value == "orange":
        return True
    if verified_value in {"green", "yellow"}:
        return False
    return None


def get_bootloader_unlock_status(serial: str) -> tuple[bool | None, str]:
    """Query whether one fastboot device has an unlocked bootloader."""
    _, stdout, stderr = _run_cmd(
        _device_command(FASTBOOT_PATH, serial, ["getvar", "unlocked"]),
        timeout=15,
    )
    detail = "\n".join(part.strip() for part in (stdout, stderr) if part and part.strip())
    return parse_bootloader_unlock_status(detail), detail


def get_adb_bootloader_unlock_status(serial: str) -> tuple[bool | None, str]:
    """Read bootloader lock properties from a running Android device."""
    properties = (
        "ro.boot.flash.locked",
        "ro.boot.verifiedbootstate",
    )
    values: dict[str, str] = {}
    details: list[str] = []

    for property_name in properties:
        _, stdout, stderr = _run_cmd(
            _device_command(ADB_PATH, serial, ["shell", "getprop", property_name]),
            timeout=10,
        )
        value = (stdout or "").strip()
        if not value:
            value = (stderr or "").strip()
        values[property_name] = value
        if value:
            details.append(f"{property_name}={value}")

    detail = "\n".join(details)
    status = parse_adb_bootloader_unlock_status(
        values.get("ro.boot.flash.locked", ""),
        values.get("ro.boot.verifiedbootstate", ""),
    )
    return status, detail
