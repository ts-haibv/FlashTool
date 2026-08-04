import os
import tempfile
import unittest

from flash_tool.profiles.auto_detect import (
    detect_device,
    detect_variant,
    get_g6_variants,
    G6_FAMILY_MODELS,
    resolve_g6_images,
)


class TestAutoDetect(unittest.TestCase):
    def test_g6_x6_x5_x5p_share_the_same_flash_family(self):
        self.assertEqual(G6_FAMILY_MODELS, {"G6", "X6", "X5", "X5P"})

    def test_resolves_g6_images_without_manual_selection(self):
        selected = resolve_g6_images(
            {
                "super": ["super.img"],
                "product_region": ["MN3/product-mn3.img"],
                "vbmeta_system": ["MN3/vbmeta_system-mn3.img"],
            }
        )

        self.assertEqual(
            selected,
            {
                "super": "super.img",
                "product": "MN3/product-mn3.img",
                "vbmeta": "MN3/vbmeta_system-mn3.img",
            },
        )

    def test_resolves_g6_images_for_selected_variant(self):
        detected = {
            "system": ["system.img"],
            "system_ext": ["system_ext-sx5p.img"],
            "product_region": ["ML2/product-ml2.img", "MN3/product-mn3.img"],
            "vbmeta_system": ["ML2/vbmeta_system-ml2.img", "MN3/vbmeta_system-mn3.img"],
        }

        self.assertEqual(get_g6_variants(detected), ["ML2", "MN3"])
        self.assertEqual(
            resolve_g6_images(detected, "ML2"),
            {
                "system": "system.img",
                "system_ext": "system_ext-sx5p.img",
                "product": "ML2/product-ml2.img",
                "vbmeta": "ML2/vbmeta_system-ml2.img",
            },
        )

    def test_detects_ps10_and_variant_from_rom_layout(self):
        with tempfile.TemporaryDirectory() as path:
            open(os.path.join(path, "system_ext-lockon.img"), "w").close()
            os.mkdir(os.path.join(path, "PDN3"))

            profiles = {
                "PS10": {
                    "variants": ["mn3", "pdn3"],
                    "variant_dirs": {"mn3": "MN3", "pdn3": "PDN3"},
                    "default_variant": "mn3",
                }
            }

            self.assertEqual(detect_device(path), "PS10")
            self.assertEqual(detect_variant(path, "PS10", profiles), "pdn3")

    def test_detects_g6_from_documented_partition_layout(self):
        with tempfile.TemporaryDirectory() as path:
            for image in ("system.img", "system_ext-ramba.img", "vbmeta.img"):
                open(os.path.join(path, image), "w").close()

            self.assertEqual(detect_device(path), "G6")

    def test_detects_x5_and_x5p_before_broad_ps11_signature(self):
        with tempfile.TemporaryDirectory() as path:
            open(os.path.join(path, "system_ext-sx5p.img"), "w").close()
            self.assertEqual(detect_device(path), "X5P")

        with tempfile.TemporaryDirectory() as path:
            open(os.path.join(path, "system_ext-sx5.img"), "w").close()
            self.assertEqual(detect_device(path), "X5")


if __name__ == "__main__":
    unittest.main()
