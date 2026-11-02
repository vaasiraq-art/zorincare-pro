"""Tests for Smart SystemCare health scoring, Driver Booster parsers, and Revo Uninstaller safety."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from zorincare.core.driver_booster import parse_lspci_nnk, parse_ubuntu_drivers_devices
from zorincare.core.root_helper import _is_safe_root_leftover
from zorincare.core.system_care import CareCategoryResult, _parse_human_size_to_bytes, compute_health_score
from zorincare.core.uninstaller import InstalledApp, extract_app_tokens, scan_app_leftovers


SAMPLE_UBUNTU_DRIVERS = """
== /sys/devices/pci0000:00/0000:00:01.0/0000:01:00.0 ==
modalias : pci:v000010DEd00002684sv00001043sd000088ACbc03sc00i00
vendor   : NVIDIA Corporation
model    : AD102 [GeForce RTX 4090]
driver   : nvidia-driver-550 - distro non-free
driver   : nvidia-driver-560 - distro non-free recommended
driver   : xserver-xorg-video-nouveau - distro free builtin
"""

SAMPLE_LSPCI_NNK = """
00:00.0 Host bridge [0600]: Intel Corporation Device [8086:a700]
01:00.0 VGA compatible controller [0300]: NVIDIA Corporation AD102 [GeForce RTX 4090] [10de:2684] (rev a1)
\tSubsystem: ASUSTeK Computer Inc. Device [1043:88ac]
\tKernel driver in use: nvidia
\tKernel modules: nvidiafb, nouveau, nvidia_drm, nvidia
02:00.0 Network controller [0280]: Broadcom Inc. BCM4360 802.11ac Wireless [14e4:43a0] (rev 03)
\tKernel modules: bcma, wl
"""


class TestCoreEngines(unittest.TestCase):
    def test_system_care_health_score(self) -> None:
        clean_cats = [
            CareCategoryResult("apt_cache", "cat_apt_cache", "cat_apt_cache_desc", "ic", True, 0, 0),
            CareCategoryResult("trash", "cat_trash", "cat_trash_desc", "ic", False, 0, 0),
        ]
        self.assertEqual(compute_health_score(clean_cats), 100)

        dirty_cats = [
            CareCategoryResult("apt_cache", "cat_apt_cache", "cat_apt_cache_desc", "ic", True, 12, 850 * 1024**2),
            CareCategoryResult("crash_dumps", "cat_crash_dumps", "cat_crash_dumps_desc", "ic", True, 2, 40 * 1024**2),
        ]
        score = compute_health_score(dirty_cats)
        self.assertLess(score, 85)
        self.assertGreaterEqual(score, 38)

    def test_human_size_parser(self) -> None:
        self.assertEqual(_parse_human_size_to_bytes("After this operation, 250 MB disk space will be freed."), 250 * 1024**2)
        self.assertEqual(_parse_human_size_to_bytes("Archived and active journals take up 1.5G"), 0)
        self.assertEqual(_parse_human_size_to_bytes("1.5 GiB"), int(1.5 * 1024**3))

    def test_ubuntu_drivers_parser(self) -> None:
        devs = parse_ubuntu_drivers_devices(SAMPLE_UBUNTU_DRIVERS, installed_pkgs={"nvidia-driver-550"})
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0].vendor, "NVIDIA Corporation")
        # Recommended should be sorted first
        self.assertEqual(devs[0].options[0].package, "nvidia-driver-560")
        self.assertTrue(devs[0].options[0].recommended)
        self.assertFalse(devs[0].options[0].installed)
        self.assertTrue(any(o.package == "nvidia-driver-550" and o.installed for o in devs[0].options))

    def test_lspci_missing_driver_detection(self) -> None:
        items = parse_lspci_nnk(SAMPLE_LSPCI_NNK)
        self.assertEqual(len(items), 2)  # Host bridge filtered out
        gpu = items[0]
        wifi = items[1]
        self.assertEqual(gpu.driver_in_use, "nvidia")
        self.assertFalse(gpu.missing_driver)
        self.assertEqual(wifi.driver_in_use, "")
        self.assertTrue(wifi.missing_driver)

    def test_revo_leftover_scanner_and_protection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            # Create protected GNOME/Zorin directories that must NEVER be touched
            (home / ".config" / "dconf").mkdir(parents=True)
            (home / ".config" / "gtk-4.0").mkdir(parents=True)
            (home / ".config" / "zorincare-pro").mkdir(parents=True)

            # Create fake VLC leftovers
            vlc_cfg = home / ".config" / "vlc"
            vlc_cfg.mkdir(parents=True)
            (vlc_cfg / "vlcrc").write_text("volume=100\n", encoding="utf-8")

            vlc_fp = home / ".var" / "app" / "org.videolan.VLC"
            vlc_fp.mkdir(parents=True)
            (vlc_fp / "data.bin").write_bytes(b"x" * 2048)

            app = InstalledApp(
                name="VLC media player",
                pkg_id="org.videolan.VLC",
                source="flatpak",
                version="3.0.21",
            )
            tokens = extract_app_tokens(app)
            self.assertIn("videolan", tokens)
            self.assertNotIn("org", tokens)

            leftovers = scan_app_leftovers(app, mode="moderate", home_dir=home)
            paths = {Path(it.path).name for it in leftovers}
            self.assertIn("vlc", paths)
            self.assertIn("org.videolan.VLC", paths)
            self.assertNotIn("dconf", paths)
            self.assertNotIn("gtk-4.0", paths)
            self.assertNotIn("zorincare-pro", paths)

    def test_root_leftover_blocklist(self) -> None:
        self.assertFalse(_is_safe_root_leftover("/"))
        self.assertFalse(_is_safe_root_leftover("/etc"))
        self.assertFalse(_is_safe_root_leftover("/etc/apt"))
        self.assertFalse(_is_safe_root_leftover("/etc/apt/sources.list"))
        self.assertFalse(_is_safe_root_leftover("/etc/systemd/system"))
        self.assertFalse(_is_safe_root_leftover("/var/lib/dpkg"))
        self.assertFalse(_is_safe_root_leftover("/usr/bin"))
        if Path("/").exists() and str(Path("/opt/discord").resolve()).startswith("/opt/"):
            self.assertTrue(_is_safe_root_leftover("/opt/discord"))


if __name__ == "__main__":
    unittest.main()
