"""Unit tests for the updater module."""

import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from flash_tool.updater import (
    parse_version,
    check_for_updates,
    download_file_with_progress,
    apply_update,
)


class TestUpdater(unittest.TestCase):

    def test_parse_version(self):
        """Verify version comparison parsing formats."""
        self.assertEqual(parse_version("1.2.4"), (1, 2, 4))
        self.assertEqual(parse_version("v1.2.4"), (1, 2, 4))
        self.assertEqual(parse_version(" v1.2.4-beta "), (1, 2, 4))
        self.assertEqual(parse_version("2.0"), (2, 0))
        self.assertEqual(parse_version("v10.15.2.1"), (10, 15, 2, 1))

    @patch("ssl.create_default_context")
    @patch("urllib.request.urlopen")
    def test_check_for_updates_newer(self, mock_urlopen, mock_ssl_context):
        """Verify updates detected when a newer version exists."""
        # Mock GitHub API response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"""
        {
            "tag_name": "v1.3.0",
            "body": "Bug fixes and improvements",
            "html_url": "https://github.com/ts-haibv/FlashTool/releases/tag/v1.3.0",
            "assets": [
                {
                    "name": "FlashTool-Linux",
                    "browser_download_url": "https://github.com/ts-haibv/FlashTool/releases/download/v1.3.0/FlashTool-Linux",
                    "size": 12345
                },
                {
                    "name": "FlashTool-Windows.exe",
                    "browser_download_url": "https://github.com/ts-haibv/FlashTool/releases/download/v1.3.0/FlashTool-Windows.exe",
                    "size": 67890
                }
            ]
        }
        """
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Test on Linux
        with patch("sys.platform", "linux"):
            info = check_for_updates("1.2.4")
            self.assertIsNotNone(info)
            self.assertTrue(info["update_available"])
            self.assertEqual(info["latest_version"], "v1.3.0")
            self.assertEqual(info["asset_name"], "FlashTool-Linux")
            self.assertEqual(info["size"], 12345)

        # Test on Windows
        with patch("sys.platform", "win32"):
            info = check_for_updates("1.2.4")
            self.assertIsNotNone(info)
            self.assertTrue(info["update_available"])
            self.assertEqual(info["latest_version"], "v1.3.0")
            self.assertEqual(info["asset_name"], "FlashTool-Windows.exe")
            self.assertEqual(info["size"], 67890)

    @patch("ssl.create_default_context")
    @patch("urllib.request.urlopen")
    def test_check_for_updates_older_or_equal(self, mock_urlopen, mock_ssl_context):
        """Verify no updates detected when version is current or newer."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"tag_name": "v1.2.4"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        info = check_for_updates("1.2.4")
        self.assertIsNotNone(info)
        self.assertFalse(info["update_available"])

        info = check_for_updates("1.3.0")
        self.assertIsNotNone(info)
        self.assertFalse(info["update_available"])

    def test_apply_update_not_frozen(self):
        """Verify update is rejected when not running frozen executable."""
        with patch("sys.frozen", False, create=True):
            self.assertFalse(apply_update("dummy_path"))

    def test_apply_update_frozen_linux(self):
        """Verify executable replacement procedure on Linux."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dummy_exe = os.path.join(tmpdir, "FlashTool-Linux")
            new_exe = os.path.join(tmpdir, "new_update")

            with open(dummy_exe, "w") as f:
                f.write("old version")
            with open(new_exe, "w") as f:
                f.write("new version")

            with patch("sys.executable", dummy_exe), \
                 patch("sys.frozen", True, create=True), \
                 patch("sys.platform", "linux"), \
                 patch("os.chmod") as mock_chmod:

                success = apply_update(new_exe)
                self.assertTrue(success)

                # Check executable has been replaced
                with open(dummy_exe, "r") as f:
                    content = f.read()
                self.assertEqual(content, "new version")

                # Linux deletes the .bak immediately in our logic
                self.assertFalse(os.path.exists(dummy_exe + ".bak"))
                mock_chmod.assert_called_once_with(dummy_exe, 0o755)

    def test_apply_update_frozen_windows(self):
        """Verify executable renaming procedure on Windows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dummy_exe = os.path.join(tmpdir, "FlashTool.exe")
            new_exe = os.path.join(tmpdir, "new_update")

            with open(dummy_exe, "w") as f:
                f.write("old version")
            with open(new_exe, "w") as f:
                f.write("new version")

            with patch("sys.executable", dummy_exe), \
                 patch("sys.frozen", True, create=True), \
                 patch("sys.platform", "win32"):

                success = apply_update(new_exe)
                self.assertTrue(success)

                # Check executable has been replaced
                with open(dummy_exe, "r") as f:
                    content = f.read()
                self.assertEqual(content, "new version")

                # Windows retains the backup exe to be cleaned up on next run
                self.assertTrue(os.path.exists(dummy_exe + ".bak"))
                with open(dummy_exe + ".bak", "r") as f:
                    bak_content = f.read()
                self.assertEqual(bak_content, "old version")


if __name__ == "__main__":
    unittest.main()
