import unittest
from unittest.mock import call, patch

from flash_tool.config import ADB_PATH, FASTBOOT_PATH
from flash_tool.device_manager import (
    get_adb_bootloader_unlock_status,
    get_bootloader_unlock_status,
    parse_adb_bootloader_unlock_status,
    parse_bootloader_unlock_status,
    reboot_to_bootloader,
    unlock_bootloader,
)
from flash_tool.profiles.g6_ramba import build_g6_ramba_steps, build_suw_only_steps


class TestBootloaderCommand(unittest.TestCase):
    @patch("flash_tool.device_manager._run_cmd")
    def test_reboots_adb_device_into_the_bootloader(self, run_cmd):
        run_cmd.return_value = (0, "", "")

        success, detail = reboot_to_bootloader("ABC123")

        self.assertTrue(success)
        self.assertEqual(detail, "")
        run_cmd.assert_called_once_with(
            [
                ADB_PATH,
                "-s",
                "ABC123",
                "reboot",
                "bootloader",
            ],
        )

    @patch("flash_tool.device_manager._run_cmd")
    def test_runs_fastboot_unlock_for_the_target_device(self, run_cmd):
        run_cmd.return_value = (0, "OKAY", "")

        success, detail = unlock_bootloader("ABC123")

        self.assertTrue(success)
        self.assertEqual(detail, "OKAY")
        run_cmd.assert_called_once_with(
            [
                FASTBOOT_PATH,
                "-s",
                "ABC123",
                "flashing",
                "unlock",
            ],
            timeout=120,
        )

    @patch("flash_tool.device_manager._run_cmd")
    def test_reads_fastboot_unlock_status_for_the_target_device(self, run_cmd):
        run_cmd.return_value = (0, "", "(bootloader) unlocked: yes")

        status, detail = get_bootloader_unlock_status("ABC123")

        self.assertTrue(status)
        self.assertIn("unlocked: yes", detail)
        run_cmd.assert_called_once_with(
            [FASTBOOT_PATH, "-s", "ABC123", "getvar", "unlocked"],
            timeout=15,
        )

    def test_parses_already_unlocked_fastboot_error(self):
        self.assertTrue(
            parse_bootloader_unlock_status("FAILED (remote: 'Device already : unlocked!')")
        )
        self.assertFalse(parse_bootloader_unlock_status("(bootloader) unlocked: no"))
        self.assertIsNone(parse_bootloader_unlock_status("fastboot: error: unknown command"))

    def test_parses_android_boot_properties(self):
        self.assertTrue(parse_adb_bootloader_unlock_status("0", "orange"))
        self.assertFalse(parse_adb_bootloader_unlock_status("1", "green"))
        self.assertTrue(parse_adb_bootloader_unlock_status("", "orange"))
        self.assertFalse(parse_adb_bootloader_unlock_status("", "yellow"))
        self.assertIsNone(parse_adb_bootloader_unlock_status("", "unknown"))

    @patch("flash_tool.device_manager._run_cmd")
    def test_reads_android_boot_properties_for_the_target_device(self, run_cmd):
        run_cmd.side_effect = [
            (0, "0\n", ""),
            (0, "orange\n", ""),
        ]

        status, detail = get_adb_bootloader_unlock_status("ABC123")

        self.assertTrue(status)
        self.assertIn("ro.boot.flash.locked=0", detail)
        self.assertIn("ro.boot.verifiedbootstate=orange", detail)
        self.assertEqual(
            run_cmd.call_args_list,
            [
                call(
                    [ADB_PATH, "-s", "ABC123", "shell", "getprop", "ro.boot.flash.locked"],
                    timeout=10,
                ),
                call(
                    [ADB_PATH, "-s", "ABC123", "shell", "getprop", "ro.boot.verifiedbootstate"],
                    timeout=10,
                ),
            ],
        )


class TestG6ProfileSetup(unittest.TestCase):
    def test_profile_does_not_try_to_write_oem_unlock_flag(self):
        steps = build_g6_ramba_steps()

        self.assertEqual([step.id for step in steps], list(range(1, len(steps) + 1)))
        self.assertEqual(steps[0].name, "Reboot to Bootloader")
        self.assertNotIn("SUW", " ".join(step.name for step in steps))
        self.assertNotIn(
            "oem_unlock_allowed",
            " ".join(arg for step in steps for arg in step.args),
        )

    def test_standalone_suw_profile_marks_provisioning_and_reboots(self):
        steps = build_suw_only_steps()

        self.assertEqual([step.id for step in steps], list(range(1, 6)))
        self.assertEqual(steps[0].wait_for_device_mode, "adb")
        self.assertIn("device_provisioned", steps[1].args)
        self.assertIn("user_setup_complete", steps[2].args)
        self.assertEqual(steps[-1].args, ["reboot"])


if __name__ == "__main__":
    unittest.main()
