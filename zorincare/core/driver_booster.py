"""Driver & Firmware Booster engine for Zorin OS 18.1 Pro (ubuntu-drivers, fwupdmgr, DKMS, PCI/USB)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import platform
import re

from zorincare.core.runner import LOG_BUS, run_cmd, run_privileged, which_bin


@dataclass
class DriverOption:
    package: str
    description: str
    recommended: bool
    free: bool
    installed: bool


@dataclass
class HardwareDeviceDrivers:
    sysfs_path: str
    vendor: str
    model: str
    options: list[DriverOption] = field(default_factory=list)


@dataclass
class FirmwareUpdateItem:
    device_id: str
    name: str
    vendor: str
    current_version: str
    target_version: str
    summary: str


@dataclass
class StackHealthReport:
    kernel_version: str
    cpu_vendor: str
    microcode_pkg: str
    microcode_installed: bool
    hwe_kernel_installed: bool
    vulkan_installed: bool
    restricted_codecs_installed: bool
    restricted_codecs_pkg: str
    dkms_summary: list[str]
    dkms_has_warning: bool


@dataclass
class PciHardwareItem:
    slot: str
    category: str
    device_name: str
    driver_in_use: str
    kernel_modules: str

    @property
    def missing_driver(self) -> bool:
        relevant = any(
            k in self.category.lower()
            for k in ("vga", "3d", "display", "network", "ethernet", "audio", "wireless")
        )
        return relevant and not self.driver_in_use and bool(self.kernel_modules)


@dataclass
class DriverScanReport:
    proprietary_devices: list[HardwareDeviceDrivers]
    firmware_updates: list[FirmwareUpdateItem]
    stack: StackHealthReport
    pci_devices: list[PciHardwareItem]
    usb_devices: list[str]


def _get_installed_dpkg_set() -> set[str]:
    installed: set[str] = set()
    if not which_bin("dpkg-query"):
        return installed
    res = run_cmd(["dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\n"], timeout=20)
    if res.ok:
        for line in res.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1].strip().startswith("ii"):
                installed.add(parts[0].split(":")[0].strip())
    return installed


def parse_ubuntu_drivers_devices(raw: str, installed_pkgs: set[str] | None = None) -> list[HardwareDeviceDrivers]:
    """Parse `ubuntu-drivers devices` text output into structured GPU/Wi-Fi driver candidates."""
    installed = installed_pkgs or set()
    devices: list[HardwareDeviceDrivers] = []
    current: HardwareDeviceDrivers | None = None

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("==") and line.endswith("=="):
            sysfs = line.strip("=").strip()
            current = HardwareDeviceDrivers(sysfs_path=sysfs, vendor="Hardware", model=sysfs)
            devices.append(current)
            continue
        if current is None:
            continue
        if line.startswith("vendor") and ":" in line:
            current.vendor = line.split(":", 1)[1].strip()
        elif line.startswith("model") and ":" in line:
            current.model = line.split(":", 1)[1].strip()
        elif line.startswith("driver") and ":" in line:
            drv_info = line.split(":", 1)[1].strip()
            # Format: nvidia-driver-560 - distro non-free recommended
            parts = [p.strip() for p in drv_info.split(" - ", 1)]
            pkg = parts[0]
            meta = parts[1] if len(parts) > 1 else ""
            rec = "recommended" in meta.lower()
            is_free = "non-free" not in meta.lower()
            is_inst = pkg in installed
            current.options.append(
                DriverOption(
                    package=pkg,
                    description=meta or "Ubuntu/Zorin Driver Repository",
                    recommended=rec,
                    free=is_free,
                    installed=is_inst,
                )
            )
    # Sort each device's options so recommended is first
    for d in devices:
        d.options.sort(key=lambda o: (not o.recommended, not o.installed, o.package))
    return [d for d in devices if d.options]


def parse_lspci_nnk(raw: str) -> list[PciHardwareItem]:
    """Parse `lspci -nnk` output into hardware controllers and active kernel drivers."""
    items: list[PciHardwareItem] = []
    current: PciHardwareItem | None = None

    header_re = re.compile(r"^([0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F])\s+([^:]+):\s+(.+)$")
    for raw_line in raw.splitlines():
        if not raw_line.strip():
            continue
        if not raw_line.startswith("\t") and not raw_line.startswith(" "):
            m = header_re.match(raw_line.strip())
            if m:
                slot, cat, name = m.group(1), m.group(2).strip(), m.group(3).strip()
                # Filter out noisy host bridges/PCI bridges to highlight meaningful hardware
                skip_cats = ("host bridge", "pci bridge", "isa bridge", "ram memory", "smbus")
                if any(sc in cat.lower() for sc in skip_cats):
                    current = None
                    continue
                current = PciHardwareItem(
                    slot=slot,
                    category=cat,
                    device_name=name,
                    driver_in_use="",
                    kernel_modules="",
                )
                items.append(current)
        elif current is not None:
            sub = raw_line.strip()
            if sub.lower().startswith("kernel driver in use:"):
                current.driver_in_use = sub.split(":", 1)[1].strip()
            elif sub.lower().startswith("kernel modules:"):
                current.kernel_modules = sub.split(":", 1)[1].strip()

    return items


def scan_fwupd_updates() -> list[FirmwareUpdateItem]:
    updates: list[FirmwareUpdateItem] = []
    if not which_bin("fwupdmgr"):
        return updates
    res = run_cmd(["fwupdmgr", "get-updates", "--json"], timeout=30)
    if not res.ok or not res.stdout.strip():
        return updates
    try:
        data = json.loads(res.stdout)
        for dev in data.get("Devices", []):
            releases = dev.get("Releases") or []
            if not releases:
                continue
            latest = releases[0]
            updates.append(
                FirmwareUpdateItem(
                    device_id=str(dev.get("DeviceId", "")),
                    name=str(dev.get("Name", "Device")),
                    vendor=str(dev.get("Vendor", "")),
                    current_version=str(dev.get("Version", "unknown")),
                    target_version=str(latest.get("Version", "latest")),
                    summary=str(latest.get("Summary", "LVFS Firmware Update")),
                )
            )
    except Exception:
        pass
    return updates


def scan_stack_health(installed_pkgs: set[str]) -> StackHealthReport:
    cpu_vendor = "Unknown"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        try:
            txt = cpuinfo.read_text(encoding="utf-8", errors="ignore")
            if "GenuineIntel" in txt:
                cpu_vendor = "Intel"
            elif "AuthenticAMD" in txt:
                cpu_vendor = "AMD"
        except OSError:
            pass

    microcode_pkg = "amd64-microcode" if cpu_vendor == "AMD" else "intel-microcode"
    microcode_installed = microcode_pkg in installed_pkgs
    hwe_installed = (
        "linux-generic-hwe-24.04" in installed_pkgs
        or "linux-image-generic-hwe-24.04" in installed_pkgs
    )
    vulkan_installed = (
        "mesa-vulkan-drivers" in installed_pkgs or "vulkan-tools" in installed_pkgs
    )

    # Check if zorin-os-restricted-extras exists in APT cache, otherwise ubuntu-restricted-extras
    codecs_pkg = "ubuntu-restricted-extras"
    if which_bin("apt-cache"):
        chk = run_cmd(["apt-cache", "show", "zorin-os-restricted-extras"], timeout=10)
        if chk.ok and "Package: zorin-os-restricted-extras" in chk.stdout:
            codecs_pkg = "zorin-os-restricted-extras"
    codecs_installed = (
        "zorin-os-restricted-extras" in installed_pkgs
        or "ubuntu-restricted-extras" in installed_pkgs
    )

    dkms_lines: list[str] = []
    dkms_warn = False
    if which_bin("dkms"):
        dres = run_cmd(["dkms", "status"], timeout=15)
        if dres.ok and dres.stdout.strip():
            for line in dres.stdout.strip().splitlines():
                dkms_lines.append(line.strip())
                if "installed" not in line.lower():
                    dkms_warn = True

    return StackHealthReport(
        kernel_version=platform.release(),
        cpu_vendor=cpu_vendor,
        microcode_pkg=microcode_pkg,
        microcode_installed=microcode_installed,
        hwe_kernel_installed=hwe_installed,
        vulkan_installed=vulkan_installed,
        restricted_codecs_installed=codecs_installed,
        restricted_codecs_pkg=codecs_pkg,
        dkms_summary=dkms_lines,
        dkms_has_warning=dkms_warn,
    )


def run_driver_scan() -> DriverScanReport:
    LOG_BUS.emit("Scanning hardware controllers, proprietary drivers, and LVFS firmware...")
    installed_pkgs = _get_installed_dpkg_set()

    prop_devices: list[HardwareDeviceDrivers] = []
    if which_bin("ubuntu-drivers"):
        ud_res = run_cmd(["ubuntu-drivers", "devices"], timeout=45)
        if ud_res.ok:
            prop_devices = parse_ubuntu_drivers_devices(ud_res.stdout, installed_pkgs)

    fw_updates = scan_fwupd_updates()
    stack = scan_stack_health(installed_pkgs)

    pci_items: list[PciHardwareItem] = []
    if which_bin("lspci"):
        pci_res = run_cmd(["lspci", "-nnk"], timeout=15)
        if pci_res.ok:
            pci_items = parse_lspci_nnk(pci_res.stdout)

    usb_items: list[str] = []
    if which_bin("lsusb"):
        usb_res = run_cmd(["lsusb"], timeout=10)
        if usb_res.ok:
            for line in usb_res.stdout.splitlines():
                if "root hub" not in line.lower() and line.strip():
                    usb_items.append(line.strip())

    LOG_BUS.emit(
        f"Driver scan complete: {len(prop_devices)} proprietary device group(s), "
        f"{len(fw_updates)} firmware update(s), {len(pci_items)} PCI controller(s)."
    )
    return DriverScanReport(
        proprietary_devices=prop_devices,
        firmware_updates=fw_updates,
        stack=stack,
        pci_devices=pci_items,
        usb_devices=usb_items,
    )


def install_recommended_drivers() -> tuple[bool, str]:
    res = run_privileged("install_drivers_auto", {}, timeout=900)
    return res.ok, res.combined_output


def install_driver_packages(packages: list[str]) -> tuple[bool, str]:
    res = run_privileged("apt_install", {"packages": packages}, timeout=900)
    return res.ok, res.combined_output


def update_all_firmware() -> tuple[bool, str]:
    res = run_privileged("fwupd_update", {}, timeout=900)
    return res.ok, res.combined_output
