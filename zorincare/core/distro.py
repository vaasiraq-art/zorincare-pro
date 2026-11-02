"""System and distribution detection tailored for Zorin OS 18.1 Pro (Ubuntu 24.04 Noble)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import platform
import socket


@dataclass
class SystemProfile:
    distro_name: str
    distro_id: str
    distro_version: str
    ubuntu_codename: str
    is_zorin: bool
    kernel: str
    arch: str
    hostname: str
    desktop: str
    session_type: str
    cpu_model: str
    cpu_cores: int
    total_ram_bytes: int
    is_linux: bool


def _parse_os_release(content: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def detect_system_profile() -> SystemProfile:
    is_linux = platform.system().lower() == "linux"
    os_rel: dict[str, str] = {}
    os_release_path = Path("/etc/os-release")
    if is_linux and os_release_path.exists():
        try:
            os_rel = _parse_os_release(os_release_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pass

    distro_name = os_rel.get("PRETTY_NAME") or platform.platform()
    distro_id = os_rel.get("ID", "linux" if is_linux else platform.system().lower())
    distro_version = os_rel.get("VERSION_ID", "")
    ubuntu_codename = os_rel.get("UBUNTU_CODENAME") or os_rel.get("VERSION_CODENAME", "")
    is_zorin = "zorin" in distro_id.lower() or "zorin" in distro_name.lower()

    cpu_model = platform.processor() or "Unknown CPU"
    if is_linux and Path("/proc/cpuinfo").exists():
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.lower().startswith("model name") and ":" in line:
                    cpu_model = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass

    total_ram = 0
    if is_linux and Path("/proc/meminfo").exists():
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        total_ram = int(parts[1]) * 1024
                    break
        except Exception:
            pass

    return SystemProfile(
        distro_name=distro_name,
        distro_id=distro_id,
        distro_version=distro_version,
        ubuntu_codename=ubuntu_codename,
        is_zorin=is_zorin,
        kernel=platform.release(),
        arch=platform.machine(),
        hostname=socket.gethostname(),
        desktop=os.environ.get("XDG_CURRENT_DESKTOP", "GNOME"),
        session_type=os.environ.get("XDG_SESSION_TYPE", "wayland"),
        cpu_model=cpu_model,
        cpu_cores=os.cpu_count() or 1,
        total_ram_bytes=total_ram,
        is_linux=is_linux,
    )
