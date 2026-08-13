import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


JENKINS_PROFILES = (
    {
        "name": "PS10",
        "script": "flash_ps10.sh",
        "asset": "ps10",
        "args": ("-v", "mn3", "--rom-type", "jenkins", "-n", "-y"),
        "model_dir": "MN3",
        "images": ("system.img", "system_ext-lockon.img", "pvmfw.img"),
        "model_images": ("product-mn3.img", "vbmeta_system-mn3.img"),
        "has_exact_asset": True,
    },
    {
        "name": "E9",
        "script": "flash_e9.sh",
        "asset": "e9",
        "args": ("--model", "MC4", "--rom-type", "jenkins", "--dry-run", "-y"),
        "model_dir": "MC4",
        "images": (
            "init_boot.img",
            "pvmfw.img",
            "system.img",
            "system_ext-naze.img",
        ),
        "model_images": ("product-mc4.img", "vbmeta_system-mc4.img"),
        "has_exact_asset": False,
    },
    {
        "name": "E10",
        "script": "flash_e10.sh",
        "asset": "e10",
        "args": ("--model", "MC5", "--rom-type", "jenkins", "--dry-run", "-y"),
        "model_dir": "MC5",
        "images": (
            "init_boot.img",
            "pvmfw.img",
            "system.img",
            "system_ext-lyle.img",
        ),
        "model_images": ("product-mc5.img", "vbmeta_system-mc5.img"),
        "has_exact_asset": False,
    },
    {
        "name": "E11",
        "script": "flash_e11.sh",
        "asset": "e11",
        "args": ("--model", "MC6", "--rom-type", "jenkins", "--dry-run", "-y"),
        "model_dir": "MC6",
        "images": (
            "init_boot.img",
            "pvmfw.img",
            "system.img",
            "system_ext-suletta.img",
        ),
        "model_images": ("product-mc6.img", "vbmeta_system-mc6.img"),
        "has_exact_asset": True,
    },
    {
        "name": "PS11",
        "script": "flash_ps11.sh",
        "asset": "ps11",
        "args": ("-v", "mn4", "--rom-type", "jenkins", "-n", "-y"),
        "model_dir": "MN4",
        "images": (
            "init_boot.img",
            "system.img",
            "system_ext-kira.img",
            "pvmfw.img",
        ),
        "model_images": ("product-mn4.img", "vbmeta_system-mn4.img"),
        "has_exact_asset": False,
    },
)


class TestJenkinsAssetMatrix(unittest.TestCase):
    def _create_fixture(self, profile, include_asset, rom_vbmeta=False):
        temp_dir = tempfile.TemporaryDirectory()
        firmware = Path(temp_dir.name)
        app_root = firmware / "app"
        app_root.mkdir()

        source_script = REPO_ROOT / profile["script"]
        script_text = source_script.read_text()
        script_text = script_text.replace(
            f'local deb_dir="/usr/share/FlashTool/assets/{profile["asset"]}"',
            f'local deb_dir="{firmware / "missing-deb-assets"}"',
        )
        isolated_script = app_root / profile["script"]
        isolated_script.write_text(script_text)

        if include_asset:
            bundled_asset = REPO_ROOT / "assets" / profile["asset"]
            destination = app_root / "assets" / profile["asset"]
            if (bundled_asset / "vbmeta_verification_disabled.img").is_file():
                shutil.copytree(bundled_asset, destination)
            else:
                # E9/E10 intentionally have no production asset yet. This
                # marker only exercises the missing-core-image path without
                # borrowing another model's vbmeta image.
                destination.mkdir(parents=True)
                (destination / "vbmeta_verification_disabled.img").write_bytes(
                    b"test-fixture"
                )

        model_dir = firmware / profile["model_dir"]
        model_dir.mkdir()
        for image in profile["images"]:
            (firmware / image).touch()
        for image in profile["model_images"]:
            if image.startswith("vbmeta_system-"):
                (model_dir / image).write_bytes(
                    b"AVB0\0\0\0\1"
                    b"SHARP/Aquos/Aquos:17/A8110/00.00.00:userdebug/test-keys"
                )
            else:
                (model_dir / image).touch()

        if rom_vbmeta:
            (firmware / "vbmeta_verification_disabled.img").write_bytes(
                b"AVB0\0\0\0\1"
                b"SHARP/Aquos/Aquos:17/A8110/00.00.00:userdebug/test-keys"
            )

        return temp_dir, firmware, isolated_script

    def test_jenkins_vbmeta_resolution_and_fatal_missing_asset_matrix(self):
        spec_text = (REPO_ROOT / "FlashTool.spec").read_text()
        for profile in JENKINS_PROFILES:
            with self.subTest(profile=profile["name"]):
                script_text = (REPO_ROOT / profile["script"]).read_text()
                if profile["name"] == "PS11":
                    self.assertIn("preserving existing base vbmeta", script_text.lower())
                else:
                    self.assertIn(
                        f'"$SCRIPT_ABS/assets/{profile["asset"]}"',
                        script_text,
                    )

                temp_dir, firmware, isolated_script = self._create_fixture(
                    profile, profile["has_exact_asset"]
                )
                try:
                    env = os.environ.copy()
                    env["FLASH_FIRMWARE_DIR"] = str(firmware)
                    result = subprocess.run(
                        ["bash", str(isolated_script), *profile["args"]],
                        cwd=REPO_ROOT,
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                finally:
                    temp_dir.cleanup()

                output = result.stdout + result.stderr
                if profile["has_exact_asset"]:
                    self.assertEqual(result.returncode, 0, output)
                    self.assertNotIn("Missing bundled", output)
                    self.assertIn("vbmeta_a", output)
                elif profile["name"] == "PS11":
                    self.assertEqual(result.returncode, 0, output)
                    self.assertNotIn("vbmeta_a", output)
                else:
                    self.assertNotEqual(result.returncode, 0, output)
                    self.assertIn(
                        f"Missing bundled vbmeta_verification_disabled.img for {profile['name']} Jenkins flash",
                        output,
                    )

        self.assertIn("ROM_ASSET_PROFILES = ('e9', 'e10', 'e11', 'ps10', 'ps11')", spec_text)

    def test_jenkins_core_image_missing_is_fatal_matrix(self):
        for profile in JENKINS_PROFILES:
            with self.subTest(profile=profile["name"]):
                temp_dir, firmware, isolated_script = self._create_fixture(
                    profile, include_asset=True
                )
                (firmware / "pvmfw.img").unlink()
                try:
                    env = os.environ.copy()
                    env["FLASH_FIRMWARE_DIR"] = str(firmware)
                    result = subprocess.run(
                        ["bash", str(isolated_script), *profile["args"]],
                        cwd=REPO_ROOT,
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                finally:
                    temp_dir.cleanup()

                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("pvmfw.img", output)

    def test_ps11_jenkins_flashes_boot_critical_images(self):
        profile = next(profile for profile in JENKINS_PROFILES if profile["name"] == "PS11")
        temp_dir, firmware, isolated_script = self._create_fixture(profile, include_asset=True)
        try:
            env = os.environ.copy()
            env["FLASH_FIRMWARE_DIR"] = str(firmware)
            result = subprocess.run(
                ["bash", str(isolated_script), *profile["args"]],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            temp_dir.cleanup()

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("fastboot flash init_boot_a", output)
        self.assertIn("fastboot flash pvmfw_a", output)
        self.assertIn("Preserving existing base vbmeta", output)

    def test_ps11_jenkins_ignores_rom_local_vbmeta_without_disable_request(self):
        profile = next(profile for profile in JENKINS_PROFILES if profile["name"] == "PS11")
        temp_dir, firmware, isolated_script = self._create_fixture(
            profile, include_asset=True, rom_vbmeta=True
        )
        try:
            env = os.environ.copy()
            env["FLASH_FIRMWARE_DIR"] = str(firmware)
            result = subprocess.run(
                ["bash", str(isolated_script), *profile["args"]],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            temp_dir.cleanup()

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Preserving existing base vbmeta", output)
        self.assertNotIn("vbmeta_a", output)

    def test_ps11_jenkins_uses_rom_local_vbmeta_when_disable_is_explicit(self):
        profile = next(profile for profile in JENKINS_PROFILES if profile["name"] == "PS11")
        temp_dir, firmware, isolated_script = self._create_fixture(
            profile, include_asset=True, rom_vbmeta=True
        )
        try:
            env = os.environ.copy()
            env["FLASH_FIRMWARE_DIR"] = str(firmware)
            result = subprocess.run(
                ["bash", str(isolated_script), *profile["args"], "--disable-avb"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            temp_dir.cleanup()

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Using ROM-local vbmeta with verification disabled", output)
        self.assertIn(
            "fastboot flash --disable-verity --disable-verification vbmeta_a",
            output,
        )

    def test_ps11_jenkins_requires_rom_local_asset_when_avb_disable_is_explicit(self):
        profile = next(profile for profile in JENKINS_PROFILES if profile["name"] == "PS11")
        temp_dir, firmware, isolated_script = self._create_fixture(profile, include_asset=True)
        try:
            env = os.environ.copy()
            env["FLASH_FIRMWARE_DIR"] = str(firmware)
            result = subprocess.run(
                ["bash", str(isolated_script), *profile["args"], "--disable-avb"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            temp_dir.cleanup()

        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("AVB disable requested", output)
        self.assertNotIn("vbmeta_a", output)

    def test_ps11_jenkins_missing_init_boot_is_fatal(self):
        profile = next(profile for profile in JENKINS_PROFILES if profile["name"] == "PS11")
        temp_dir, firmware, isolated_script = self._create_fixture(profile, include_asset=True)
        (firmware / "init_boot.img").unlink()
        try:
            env = os.environ.copy()
            env["FLASH_FIRMWARE_DIR"] = str(firmware)
            result = subprocess.run(
                ["bash", str(isolated_script), *profile["args"]],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            temp_dir.cleanup()

        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("init_boot.img", output)
        self.assertIn("critical image(s) missing", output)

    def test_local_and_release_deb_builds_share_asset_matrix(self):
        expected_loop = "for profile in e9 e10 e11 ps10 ps11;"
        local_build = (REPO_ROOT / "scripts/build_linux.sh").read_text()
        release_workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text()

        for source in (local_build, release_workflow):
            self.assertIn(expected_loop, source)
            self.assertIn("assets/$profile", source)


if __name__ == "__main__":
    unittest.main()
