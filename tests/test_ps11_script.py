import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PS11_SCRIPT = REPO_ROOT / "flash_ps11.sh"


class TestPS11Script(unittest.TestCase):
    def _run_shell_function(self, function_call):
        script_text = PS11_SCRIPT.read_text()
        script_without_main = script_text.rsplit('\nmain "$@"', 1)[0] + "\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_script = Path(temp_dir) / "flash_ps11.sh"
            isolated_script.write_text(script_without_main)
            return subprocess.run(
                ["bash", "-c", f"source {shlex.quote(str(isolated_script))}; {function_call}"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_jenkins_base_compatibility_allows_a8070_for_a8110_same_major(self):
        mismatched = self._run_shell_function(
            "ps11_jenkins_base_compatible "
            "'SHARP/Aquos/Aquos:17/A8110/00.00.00:userdebug/test-keys' "
            "'SHARP/SH-M35/Kira:17/A8070/00.00.00:userdebug/test-keys'"
        )
        self.assertEqual(mismatched.returncode, 0, mismatched.stdout + mismatched.stderr)

        different_major = self._run_shell_function(
            "ps11_jenkins_base_compatible "
            "'SHARP/Aquos/Aquos:17/A8110/00.00.00:userdebug/test-keys' "
            "'SHARP/SH-M35/Kira:16/A8070/00.00.00:userdebug/test-keys'"
        )
        self.assertNotEqual(different_major.returncode, 0, different_major.stdout + different_major.stderr)

    def test_post_flash_verification_accepts_matching_adb_build(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            fake_bin = temp_root / "bin"
            fake_bin.mkdir()
            (fake_bin / "adb").write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == devices ]]; then printf 'FAKE123\\tdevice\\n'; exit 0; fi\n"
                "if [[ \"$1\" == shell && \"$2\" == getprop ]]; then echo \"${FAKE_FINGERPRINT}\"; exit 0; fi\n"
                "exit 1\n"
            )
            (fake_bin / "fastboot").write_text("#!/usr/bin/env bash\nexit 1\n")
            (fake_bin / "adb").chmod(0o755)
            (fake_bin / "fastboot").chmod(0o755)

            script_text = PS11_SCRIPT.read_text()
            script_without_main = script_text.rsplit('\nmain "$@"', 1)[0] + "\n"
            isolated_script = temp_root / "flash_ps11.sh"
            isolated_script.write_text(script_without_main)
            expected = "SHARP/Aquos/Aquos:17/A8110/00.00.00:userdebug/test-keys"
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"
            env["FAKE_FINGERPRINT"] = "SHARP/SH-M35/Kira:17/A8070/00.00.00:userdebug/test-keys"
            command = (
                f"source {shlex.quote(str(isolated_script))}; "
                "FASTBOOT=fastboot; USE_SUDO=false; DEVICE_SERIAL=''; "
                f"verify_jenkins_boot {shlex.quote(expected)} 1"
            )
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Jenkins Android build booted successfully", result.stdout + result.stderr)

    def _run_wait_for_fastbootd(self, userspace):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            fake_fastboot = temp_root / "fastboot"
            fake_fastboot.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"devices\" ]]; then\n"
                "    echo 'FAKE123\\tfastboot'\n"
                "elif [[ \"$1\" == \"getvar\" && \"$2\" == \"is-userspace\" ]]; then\n"
                "    echo \"is-userspace: ${FAKE_USERSPACE}\" >&2\n"
                "else\n"
                "    exit 1\n"
                "fi\n"
            )
            fake_fastboot.chmod(0o755)

            script_text = PS11_SCRIPT.read_text()
            script_without_main = script_text.rsplit('\nmain "$@"', 1)[0] + "\n"
            isolated_script = temp_root / "flash_ps11.sh"
            isolated_script.write_text(script_without_main)

            env = os.environ.copy()
            env["FAKE_USERSPACE"] = userspace
            command = (
                f"source {shlex.quote(str(isolated_script))}; "
                f"FASTBOOT={shlex.quote(str(fake_fastboot))}; "
                "USE_SUDO=false; DRY_RUN=false; "
                "wait_for_device fastbootd 1"
            )
            return subprocess.run(
                ["bash", "-c", command],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_jenkins_dry_run_preserves_base_vbmeta_by_default(self):
        spec_text = (REPO_ROOT / "FlashTool.spec").read_text()
        script_text = PS11_SCRIPT.read_text()
        self.assertIn("ROM_ASSET_PROFILES = ('e9', 'e10', 'e11', 'ps10', 'ps11')", spec_text)

        with tempfile.TemporaryDirectory() as firmware_dir:
            firmware = Path(firmware_dir)
            app_root = firmware / "app"
            bundled_vbmeta_dir = app_root / "assets" / "ps11"
            bundled_vbmeta_dir.mkdir(parents=True)
            (bundled_vbmeta_dir / "vbmeta_verification_disabled.img").write_bytes(
                b"AVB0\0\0\0\1"
                b"SHARP/Kira/Kira:15/A8010/00.00.05:userdebug/test-keys"
            )
            isolated_script = app_root / "flash_ps11.sh"
            isolated_script.write_text(
                script_text.replace(
                    'local deb_dir="/usr/share/FlashTool/assets/ps11"',
                    f'local deb_dir="{firmware / "missing-deb-assets"}"',
                )
            )
            (firmware / "MN4").mkdir()
            for image in ("init_boot.img", "system.img", "system_ext-kira.img", "pvmfw.img"):
                (firmware / image).touch()
            for image in ("product-mn4.img", "vbmeta_system-mn4.img"):
                if image.startswith("vbmeta_system-"):
                    (firmware / "MN4" / image).write_bytes(
                        b"AVB0\0\0\0\1"
                        b"SHARP/Aquos/Aquos:17/A8110/00.00.00:userdebug/test-keys"
                    )
                else:
                    (firmware / "MN4" / image).touch()

            env = os.environ.copy()
            env["FLASH_FIRMWARE_DIR"] = str(firmware)
            result = subprocess.run(
                [
                    "bash",
                    str(isolated_script),
                    "-v",
                    "mn4",
                    "--rom-type",
                    "jenkins",
                    "-n",
                    "-y",
                ],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Preserving existing base vbmeta", output)
        self.assertNotIn(
            "fastboot flash --disable-verity --disable-verification vbmeta_a",
            output,
        )

    def test_wait_for_fastbootd_rejects_bootloader_and_accepts_userspace(self):
        bootloader = self._run_wait_for_fastbootd("no")
        bootloader_output = bootloader.stdout + bootloader.stderr
        self.assertNotEqual(bootloader.returncode, 0, bootloader_output)
        self.assertIn(
            "Timeout waiting for device in fastbootd mode",
            bootloader_output,
        )

        fastbootd = self._run_wait_for_fastbootd("yes")
        fastbootd_output = fastbootd.stdout + fastbootd.stderr
        self.assertEqual(fastbootd.returncode, 0, fastbootd_output)
        self.assertIn("Device detected in fastbootd mode", fastbootd_output)


if __name__ == "__main__":
    unittest.main()
