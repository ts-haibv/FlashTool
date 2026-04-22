"""Flash worker — executes flash steps in a background thread."""

import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from flash_tool.config import ADB_PATH, FASTBOOT_PATH
from flash_tool.device_manager import wait_for_device


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


@dataclass
class FlashStep:
    """A single flash step definition."""
    id: int
    name: str
    command: str                        # "fastboot" or "adb"
    args: list[str]                     # Command arguments
    timeout: int = 300                  # Seconds
    wait_for_device_mode: str = ""      # "fastboot", "adb", or ""
    wait_timeout: int = 120             # Device wait timeout
    user_action: str = ""               # Message to show user (e.g. "Confirm on device")
    image_key: str = ""                 # Key for auto-detected image (e.g. "vbmeta")
    image_arg_index: int = -1           # Which arg index to replace with detected file
    status: StepStatus = StepStatus.PENDING
    progress: float = 0.0              # 0.0 to 1.0
    elapsed: float = 0.0
    output: str = ""


@dataclass
class FlashProgress:
    """Progress update sent to GUI."""
    step_id: int
    status: StepStatus
    progress: float
    elapsed: float
    message: str
    output_line: str = ""


class FlashWorker(threading.Thread):
    """Executes flash steps sequentially in a background thread."""

    def __init__(
        self,
        steps: list[FlashStep],
        rom_path: str,
        detected_images: dict[str, str],
        on_progress: Callable[[FlashProgress], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        on_finished: Callable[[bool], None] | None = None,
    ):
        super().__init__(daemon=True)
        self.steps = steps
        self.rom_path = rom_path
        self.detected_images = detected_images  # {"vbmeta": "EED3/vbmeta_system-eed3.img", ...}
        self.on_progress = on_progress
        self.on_log = on_log
        self.on_finished = on_finished
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    @property
    def stopped(self):
        return self._stop_event.is_set()

    def _log(self, message: str):
        if self.on_log:
            self.on_log(message)

    def _emit_progress(self, step: FlashStep, message: str = "", output_line: str = ""):
        if self.on_progress:
            self.on_progress(FlashProgress(
                step_id=step.id,
                status=step.status,
                progress=step.progress,
                elapsed=step.elapsed,
                message=message,
                output_line=output_line,
            ))

    def _build_command(self, step: FlashStep) -> list[str]:
        """Build the full command list, resolving image paths."""
        binary = FASTBOOT_PATH if step.command == "fastboot" else ADB_PATH
        args = list(step.args)

        # Replace image placeholder with actual detected/selected file
        if step.image_key and step.image_arg_index >= 0:
            img_path = self.detected_images.get(step.image_key, "")
            if img_path:
                full_path = os.path.join(self.rom_path, img_path)
                args[step.image_arg_index] = full_path

        return [binary] + args

    def _run_step(self, step: FlashStep) -> bool:
        """Execute a single flash step. Returns True on success."""
        # ── Wait for device if needed ──
        if step.wait_for_device_mode:
            step.status = StepStatus.WAITING
            self._emit_progress(step, f"Waiting for device in {step.wait_for_device_mode} mode...")
            self._log(f"⏳ Waiting for device ({step.wait_for_device_mode})...")

            def on_tick(elapsed):
                step.elapsed = elapsed
                self._emit_progress(step, f"Waiting... {elapsed:.0f}s")

            success, serial = wait_for_device(
                step.wait_for_device_mode,
                timeout=step.wait_timeout,
                on_tick=on_tick,
            )
            if not success:
                self._log(f"❌ Device not found in {step.wait_for_device_mode} mode after {step.wait_timeout}s")
                return False
            self._log(f"✅ Device found: {serial}")

        # ── Execute command ──
        if step.command == "fastboot" and step.args == ["flashing", "unlock"]:
            return self._handle_unlock_step(step)

        cmd = self._build_command(step)
        cmd_str = " ".join(cmd)
        self._log(f"\n$ {cmd_str}")

        step.status = StepStatus.RUNNING
        step.progress = 0.0
        start_time = time.time()
        self._emit_progress(step, "Executing...")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            output_lines = []
            sparse_pattern = re.compile(r"Sending sparse '[^']+' (\d+)/(\d+)")

            for line in proc.stdout:
                if self.stopped:
                    proc.terminate()
                    return False

                line = line.rstrip()
                output_lines.append(line)
                step.elapsed = time.time() - start_time
                self._log(line)

                # Parse sparse image progress
                match = sparse_pattern.search(line)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    step.progress = current / total
                    self._emit_progress(step, f"Sending {current}/{total}", line)
                else:
                    self._emit_progress(step, output_line=line)

            proc.wait(timeout=step.timeout)
            step.elapsed = time.time() - start_time
            step.output = "\n".join(output_lines)

            if proc.returncode == 0:
                step.progress = 1.0
                return True
            else:
                # fastboot often returns 0 but check for FAILED in output
                combined = step.output.upper()
                if "FAILED" in combined and "OKAY" not in combined:
                    return False
                # If there's at least one OKAY, consider it success
                if "OKAY" in combined or "FINISHED" in combined:
                    step.progress = 1.0
                    return True
                return proc.returncode == 0

        except FileNotFoundError:
            self._log(f"❌ Binary not found: {cmd[0]}")
            return False
        except subprocess.TimeoutExpired:
            self._log(f"❌ Command timed out after {step.timeout}s")
            proc.kill()
            return False
        except Exception as e:
            self._log(f"❌ Error: {e}")
            return False

    def _handle_unlock_step(self, step: FlashStep) -> bool:
        """Handle unlock logic featuring pre-check and auto-detection."""
        binary = FASTBOOT_PATH
        step.status = StepStatus.RUNNING
        step.progress = 0.0
        start_time = time.time()

        # 1. Pre-check if already unlocked
        self._log("🔍 Checking current unlock status...")
        try:
            res = subprocess.run([binary, "getvar", "unlocked"], capture_output=True, text=True, timeout=5)
            combined = (res.stdout + res.stderr).lower()
            if "unlocked: yes" in combined:
                self._log("✅ Bootloader already unlocked, skipping step")
                self._emit_progress(step, "Already unlocked", "Skipping")
                step.progress = 1.0
                return True
        except Exception as e:
            self._log(f"⚠️ Failed to check unlock status: {e}")

        # 2. Not unlocked, need user action
        self._emit_progress(step, "Waiting for user action...", "Please check device screen")
        self._log("\n⚠️ " + ("=" * 45))
        self._log("  MANUAL ACTION REQUIRED ON DEVICE SCREEN:")
        self._log("  ➡ Press Vol-DOWN to select 'Unlock'")
        self._log("  ➡ Press POWER to confirm")
        self._log("=" * 45 + "\n")

        # Run unlock command
        cmd = [binary, "flashing", "unlock"]
        self._log(f"$ {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=step.timeout)
            out = proc.stdout + proc.stderr
            self._log(out)
            out_lower = out.lower()

            # fastboot returns FAILED if already unlocked — treat as success
            if "already" in out_lower and "unlock" in out_lower:
                self._log("✅ Device already unlocked — continuing")
                step.progress = 1.0
                return True

            # OKAY means the unlock command was accepted by the device
            if "okay" in out_lower:
                self._log("✅ Bootloader unlock accepted (OKAY)")
                step.progress = 1.0
                return True

        except subprocess.TimeoutExpired:
            self._log("❌ Timeout starting unlock command")
            return False
        except Exception as e:
            self._log(f"❌ Error during unlock command: {e}")
            return False

        # 3. Poll until unlocked — device may reboot after unlock prompt
        self._log("⏳ Polling unlock status... (waiting for user to confirm)")
        self._log("   Device may reboot after confirming — this is normal")
        deadline = time.time() + 90  # wait up to 90s (device may reboot)

        while time.time() < deadline:
            if self.stopped:
                return False

            elapsed = time.time() - start_time
            step.elapsed = elapsed
            self._emit_progress(step, f"Waiting for confirmation... {elapsed:.0f}s")

            try:
                res = subprocess.run([binary, "getvar", "unlocked"], capture_output=True, text=True, timeout=5)
                combined = (res.stdout + res.stderr).lower()
                if "unlocked: yes" in combined:
                    self._log("✅ Bootloader unlock confirmed!")
                    self._emit_progress(step, "Unlock confirmed")
                    step.progress = 1.0
                    return True
            except Exception:
                # Device might be rebooting or temporarily disconnected
                pass

            time.sleep(3)

        self._log("❌ Timeout waiting for unlock confirmation")
        return False

    def run(self):
        """Execute all steps sequentially."""
        self._log(f"{'═' * 60}")
        self._log(f"  FlashTool — Starting flash process")
        self._log(f"  ROM: {self.rom_path}")
        self._log(f"{'═' * 60}\n")

        all_success = True

        for step in self.steps:
            if self.stopped:
                self._log("\n⚠️  Flash process stopped by user.")
                all_success = False
                break

            self._log(f"\n{'─' * 50}")
            self._log(f"  Step {step.id}: {step.name}")
            self._log(f"{'─' * 50}")

            step.status = StepStatus.RUNNING
            self._emit_progress(step, "Starting...")

            success = self._run_step(step)

            if success:
                step.status = StepStatus.SUCCESS
                step.progress = 1.0
                self._emit_progress(step, "Done ✅")
                self._log(f"✅ Step {step.id} completed ({step.elapsed:.1f}s)")
            else:
                step.status = StepStatus.FAILED
                self._emit_progress(step, "Failed ❌")
                self._log(f"❌ Step {step.id} FAILED")
                all_success = False
                break  # Stop on failure

        self._log(f"\n{'═' * 60}")
        if all_success:
            self._log("  ✅ Flash process completed successfully!")
        else:
            self._log("  ❌ Flash process failed or was stopped.")
        self._log(f"{'═' * 60}")

        if self.on_finished:
            self.on_finished(all_success)
