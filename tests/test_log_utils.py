import unittest

from flash_tool.log_utils import strip_ansi


class TestAnsiLogSanitizer(unittest.TestCase):
    def test_removes_styles_from_bootloader_log(self):
        raw = (
            "\x1b[1m\x1b[0;35m◆ PHASE: 1 — BOOTSTRAP (bootloader mode)\x1b[0m\n"
            "\x1b[0;36m  ℹ  \x1b[0mWaiting for device in \x1b[1mfastboot\x1b[0m mode"
        )

        self.assertEqual(
            strip_ansi(raw),
            "◆ PHASE: 1 — BOOTSTRAP (bootloader mode)\n"
            "  ℹ  Waiting for device in fastboot mode",
        )

    def test_removes_cursor_and_terminal_title_sequences(self):
        raw = "\x1b[2K\x1b[1GDevice detected\x1b]0;FlashTool\x07"

        self.assertEqual(strip_ansi(raw), "Device detected")

    def test_preserves_plain_text(self):
        text = "Bootloader: UNLOCKED\nDevice product: lockon"

        self.assertEqual(strip_ansi(text), text)
