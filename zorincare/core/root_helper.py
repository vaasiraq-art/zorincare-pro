#!/usr/bin/env python3
"""Privileged Polkit helper for ZorinCare Pro.

Only executes strictly validated administrative actions with safety blocklists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import re
import shutil
import subprocess
import sys

SAFE_PKG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.+_:-]{0,127}$")
SAFE_UNIT_RE = re.compile(r"^[a-zA-Z0-9_.@-]{1,128}(\.(service|socket|timer))?$")
SAFE_CONN_RE = re.compile(r"^[^\x00\r\n]{1,128}$")

PROTECTED_PACKAGES = {
    "apt",
    "base-files",
    "bash",
    "coreutils",
    "dbus",
    "dpkg",
    "gdm3",
    "gir1.2-adw-1",
    "gir1.2-gtk-4.0",
    "gnome-shell",
    "grub-common",
    "grub-efi-amd64",
    "grub-pc",
    "init",
    "libc6",
    "linux-base",
    "linux-generic",
    "linux-generic-hwe-24.04",
    "login",
    "mount",
    "network-manager",
    "passwd",
    "policykit-1",
    "polkitd",
    "pkexec",
    "python3",
    "python3-gi",
    "sudo",
    "systemd",
    "systemd-sysv",
    "ubuntu-desktop",
    "ubuntu-minimal",
    "udev",
    "util-linux",
    "zorin-os-desktop",
    "zorin-os-minimal",
    "zorin-os-pro",
    "zorin-appearance",
}

ALLOWED_SYSCTL_KEYS = {
    "vm.swappiness",
    "vm.vfs_cache_pressure",
    "vm.dirty_ratio",
    "vm.dirty_background_ratio",
    "net.ipv4.tcp_congestion_control",
    "net.core.default_qdisc",
    "vm.max_map_count",
}

ALLOWED_ROOT_LEFTOVER_PARENTS = (
    "/etc/",
    "/var/lib/",
    "/var/cache/",
    "/var/log/",
    "/opt/",
)

FORBIDDEN_ROOT_PATHS = {
    "/",
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/etc/X11",
    "/etc/alternatives",
    "/etc/apt",
    "/etc/dbus-1",
    "/etc/default",
    "/etc/environment",
    "/etc/fstab",
    "/etc/gdm3",
    "/etc/group",
    "/etc/hostname",
    "/etc/hosts",
    "/etc/init.d",
    "/etc/ld.so.conf.d",
    "/etc/ModemManager",
    "/etc/netplan",
    "/etc/NetworkManager",
    "/etc/pam.d",
    "/etc/passwd",
    "/etc/polkit-1",
    "/etc/profile",
    "/etc/resolv.conf",
    "/etc/security",
    "/etc/shadow",
    "/etc/skel",
    "/etc/ssh",
    "/etc/ssl",
    "/etc/sudoers",
    "/etc/sudoers.d",
    "/etc/sysctl.conf",
    "/etc/sysctl.d",
    "/etc/systemd",
    "/etc/udev",
    "/etc/ufw",
    "/home",
    "/lib",
    "/lib64",
    "/opt",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/snap",
    "/srv",
    "/sys",
    "/tmp",
    "/usr",
    "/var",
    "/var/cache",
    "/var/cache/apt",
    "/var/cache/debconf",
    "/var/lib",
    "/var/lib/AccountsService",
    "/var/lib/NetworkManager",
    "/var/lib/apt",
    "/var/lib/dbus",
    "/var/lib/dkms",
    "/var/lib/dpkg",
    "/var/lib/flatpak",
    "/var/lib/fwupd",
    "/var/lib/gdm3",
    "/var/lib/polkit-1",
    "/var/lib/snapd",
    "/var/lib/systemd",
    "/var/log",
    "/var/log/apt",
    "/var/log/journal",
}


def _run(cmd: list[str], env_extra: dict[str, str] | None = None) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["LC_ALL"] = "C.UTF-8"
    env["LANG"] = "C.UTF-8"
    env["DEBIAN_FRONTEND"] = "noninteractive"
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return proc.returncode, proc.stdout, proc.stderr


def _is_safe_root_leftover(raw_path: str) -> bool:
    try:
        resolved = str(Path(raw_path).resolve())
    except Exception:
        return False
    if resolved in FORBIDDEN_ROOT_PATHS:
        return False
    for forbidden in FORBIDDEN_ROOT_PATHS:
        if forbidden not in ("/", "/etc", "/var", "/var/lib", "/var/cache", "/var/log", "/opt"):
            if resolved == forbidden or resolved.startswith(forbidden + "/"):
                return False
    if not any(resolved.startswith(prefix) for prefix in ALLOWED_ROOT_LEFTOVER_PARENTS):
        return False
    # Must be at least depth 2 under allowed parent (e.g. /opt/myapp, /etc/myapp)
    parts = [p for p in resolved.split("/") if p]
    return len(parts) >= 2


def handle_system_care_clean(payload: dict[str, Any]) -> int:
    categories: list[str] = payload.get("categories", [])
    logs: list[str] = []

    if "apt_cache" in categories and shutil.which("apt-get"):
        rc, out, err = _run(["apt-get", "clean"])
        logs.append(f"apt-get clean -> rc={rc}")

    if "apt_orphans" in categories and shutil.which("apt-get"):
        rc, out, err = _run(["apt-get", "autoremove", "--purge", "-y"])
        logs.append(f"apt-get autoremove -> rc={rc}")

    if "dpkg_rc" in categories and shutil.which("dpkg"):
        rc, out, _ = _run(["dpkg", "-l"])
        rc_pkgs = []
        if rc == 0:
            for line in out.splitlines():
                if line.startswith("rc "):
                    cols = line.split()
                    if len(cols) >= 2 and SAFE_PKG_RE.match(cols[1]) and cols[1] not in PROTECTED_PACKAGES:
                        rc_pkgs.append(cols[1])
        if rc_pkgs:
            rc2, _, _ = _run(["dpkg", "--purge"] + rc_pkgs)
            logs.append(f"dpkg --purge ({len(rc_pkgs)} residual packages) -> rc={rc2}")

    if "snap_disabled" in categories and shutil.which("snap"):
        rc, out, _ = _run(["snap", "list", "--all"])
        if rc == 0:
            for line in out.splitlines()[1:]:
                cols = line.split()
                if len(cols) >= 6 and "disabled" in cols[5]:
                    snap_name, rev = cols[0], cols[2]
                    if SAFE_PKG_RE.match(snap_name) and rev.isdigit():
                        _run(["snap", "remove", snap_name, f"--revision={rev}"])
                        logs.append(f"Removed disabled snap {snap_name} rev {rev}")

    if "journal_logs" in categories and shutil.which("journalctl"):
        rc, _, _ = _run(["journalctl", "--vacuum-size=50M"])
        logs.append(f"journalctl --vacuum-size=50M -> rc={rc}")

    if "rotated_logs" in categories:
        var_log = Path("/var/log")
        removed = 0
        if var_log.exists():
            for item in var_log.rglob("*"):
                if item.is_file() and (
                    item.name.endswith(".gz")
                    or item.name.endswith(".old")
                    or re.search(r"\.\d+$", item.name)
                ):
                    try:
                        item.unlink()
                        removed += 1
                    except Exception:
                        pass
        logs.append(f"Removed {removed} rotated log archives")

    if "crash_dumps" in categories:
        removed = 0
        for crash_dir in (Path("/var/crash"), Path("/var/lib/systemd/coredump")):
            if crash_dir.exists():
                for item in crash_dir.iterdir():
                    if item.is_file():
                        try:
                            item.unlink()
                            removed += 1
                        except Exception:
                            pass
        logs.append(f"Removed {removed} crash dump files")

    print("\n".join(logs))
    return 0


def handle_drop_caches() -> int:
    subprocess.run(["sync"], check=False)
    drop_file = Path("/proc/sys/vm/drop_caches")
    drop_file.write_text("3\n", encoding="utf-8")
    print("Dropped clean pagecache, dentries, and inodes.")
    return 0


def handle_apply_sysctl(payload: dict[str, Any]) -> int:
    settings: dict[str, str] = payload.get("settings", {})
    lines = ["# Managed by ZorinCare Pro — Safe Desktop & Gaming Kernel Optimizations"]
    for key, val in settings.items():
        if key not in ALLOWED_SYSCTL_KEYS:
            print(f"Rejected unsupported sysctl key: {key}", file=sys.stderr)
            return 2
        sval = str(val).strip()
        if not re.match(r"^[a-zA-Z0-9_ -]{1,32}$", sval):
            print(f"Invalid sysctl value for {key}", file=sys.stderr)
            return 2
        lines.append(f"{key} = {sval}")

    conf_path = Path("/etc/sysctl.d/99-zorincare-pro.conf")
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    conf_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rc, out, err = _run(["sysctl", "--system"])
    print(out or "Applied sysctl settings.")
    if rc != 0:
        print(err, file=sys.stderr)
    return rc


def handle_reset_sysctl() -> int:
    conf_path = Path("/etc/sysctl.d/99-zorincare-pro.conf")
    if conf_path.exists():
        conf_path.unlink()
    rc, out, _ = _run(["sysctl", "--system"])
    print("Reset ZorinCare Pro sysctl overrides.")
    return rc


def handle_set_cpu_governor(payload: dict[str, Any]) -> int:
    gov = str(payload.get("governor", "schedutil")).strip()
    if gov not in ("performance", "powersave", "schedutil", "ondemand"):
        print("Invalid CPU governor", file=sys.stderr)
        return 2
    cpu_root = Path("/sys/devices/system/cpu")
    updated = 0
    if cpu_root.exists():
        for gov_file in cpu_root.glob("cpu[0-9]*/cpufreq/scaling_governor"):
            try:
                gov_file.write_text(gov + "\n", encoding="utf-8")
                updated += 1
            except Exception:
                pass
    print(f"Updated scaling_governor={gov} on {updated} CPU cores.")
    return 0


def handle_install_drivers_auto() -> int:
    if not shutil.which("ubuntu-drivers"):
        print("ubuntu-drivers is not installed.", file=sys.stderr)
        return 1
    _run(["apt-get", "update"])
    rc, out, err = _run(["ubuntu-drivers", "install"])
    print(out)
    if err:
        print(err, file=sys.stderr)
    return rc


def handle_apt_install(payload: dict[str, Any]) -> int:
    packages: list[str] = payload.get("packages", [])
    if not packages:
        return 2
    for pkg in packages:
        if not SAFE_PKG_RE.match(pkg):
            print(f"Invalid package name: {pkg}", file=sys.stderr)
            return 2
    _run(["apt-get", "update"])
    rc, out, err = _run(["apt-get", "install", "-y"] + packages)
    print(out)
    if err:
        print(err, file=sys.stderr)
    return rc


def handle_fwupd_update() -> int:
    if not shutil.which("fwupdmgr"):
        print("fwupdmgr not installed.", file=sys.stderr)
        return 1
    _run(["fwupdmgr", "refresh", "--force"])
    rc, out, err = _run(["fwupdmgr", "update", "-y"])
    print(out)
    if rc in (0, 2):  # fwupdmgr exit code 2 means "nothing to update"
        return 0
    if err:
        print(err, file=sys.stderr)
    return rc


def handle_uninstall_pkg(payload: dict[str, Any]) -> int:
    source = payload.get("source", "")
    pkg_id = str(payload.get("pkg_id", "")).strip()
    if not SAFE_PKG_RE.match(pkg_id):
        print(f"Invalid package identifier: {pkg_id}", file=sys.stderr)
        return 2
    base_pkg = pkg_id.split(":")[0]
    if base_pkg in PROTECTED_PACKAGES:
        print(f"Refusing to remove protected core OS package: {base_pkg}", file=sys.stderr)
        return 3

    if source == "apt":
        rc, out, err = _run(["apt-get", "purge", "--auto-remove", "-y", pkg_id])
        print(out)
        if err:
            print(err, file=sys.stderr)
        return rc
    if source == "snap":
        rc, out, err = _run(["snap", "remove", "--purge", pkg_id])
        print(out)
        if err:
            print(err, file=sys.stderr)
        return rc
    print(f"Unsupported root uninstall source: {source}", file=sys.stderr)
    return 2


def handle_delete_root_leftovers(payload: dict[str, Any]) -> int:
    paths: list[str] = payload.get("paths", [])
    deleted = 0
    for p_str in paths:
        if not _is_safe_root_leftover(p_str):
            print(f"Skipped protected or disallowed path: {p_str}", file=sys.stderr)
            continue
        target = Path(p_str)
        try:
            if target.is_symlink() or target.is_file():
                target.unlink()
                deleted += 1
            elif target.is_dir():
                shutil.rmtree(target)
                deleted += 1
        except Exception as exc:
            print(f"Failed deleting {p_str}: {exc}", file=sys.stderr)
    print(f"Deleted {deleted} system leftover items.")
    return 0


def handle_service_action(payload: dict[str, Any]) -> int:
    op = str(payload.get("op", "")).strip()
    unit = str(payload.get("unit", "")).strip()
    if op not in ("start", "stop", "restart", "enable", "disable"):
        print("Invalid systemctl operation", file=sys.stderr)
        return 2
    if not SAFE_UNIT_RE.match(unit):
        print("Invalid systemd unit name", file=sys.stderr)
        return 2
    rc, out, err = _run(["systemctl", op, unit])
    print(out or f"systemctl {op} {unit} completed.")
    if err:
        print(err, file=sys.stderr)
    return rc


def handle_ufw_action(payload: dict[str, Any]) -> int:
    op = str(payload.get("op", "status")).strip()
    if not shutil.which("ufw"):
        print("ufw is not installed.", file=sys.stderr)
        return 1
    if op == "enable":
        _run(["ufw", "default", "deny", "incoming"])
        _run(["ufw", "default", "allow", "outgoing"])
        rc, out, err = _run(["ufw", "--force", "enable"])
    elif op == "disable":
        rc, out, err = _run(["ufw", "disable"])
    else:
        rc, out, err = _run(["ufw", "status", "verbose"])
    print(out)
    if err:
        print(err, file=sys.stderr)
    return rc


def handle_set_dns(payload: dict[str, Any]) -> int:
    preset = str(payload.get("preset", "auto")).strip()
    dns_map = {
        "auto": ("", "no"),
        "cloudflare": ("1.1.1.1 1.0.0.1", "yes"),
        "google": ("8.8.8.8 8.8.4.4", "yes"),
        "quad9": ("9.9.9.9 149.112.112.112", "yes"),
    }
    if preset not in dns_map:
        print("Unsupported DNS preset", file=sys.stderr)
        return 2
    if not shutil.which("nmcli"):
        print("nmcli is not available.", file=sys.stderr)
        return 1

    rc, out, _ = _run(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"])
    if rc != 0 or not out.strip():
        print("No active NetworkManager connection detected.", file=sys.stderr)
        return 1

    dns_servers, ignore_auto = dns_map[preset]
    updated = 0
    for line in out.strip().splitlines():
        parts = line.split(":")
        conn_name = parts[0] if parts else ""
        conn_type = parts[1] if len(parts) > 1 else ""
        if not conn_name or conn_type == "loopback" or not SAFE_CONN_RE.match(conn_name):
            continue
        _run(["nmcli", "connection", "modify", conn_name, "ipv4.dns", dns_servers])
        _run(["nmcli", "connection", "modify", conn_name, "ipv4.ignore-auto-dns", ignore_auto])
        _run(["nmcli", "connection", "up", conn_name])
        updated += 1

    if shutil.which("resolvectl"):
        _run(["resolvectl", "flush-caches"])

    print(f"Updated DNS preset '{preset}' on {updated} active connection(s).")
    return 0


def handle_power_schedule(payload: dict[str, Any]) -> int:
    op = str(payload.get("op", "cancel")).strip()
    if op == "cancel":
        rc, out, err = _run(["shutdown", "-c"])
        print(out or "Scheduled shutdown cancelled.")
        return rc
    minutes = int(payload.get("minutes", 30))
    if minutes < 1 or minutes > 1440:
        print("Minutes out of range (1..1440).", file=sys.stderr)
        return 2
    rc, out, err = _run(["shutdown", f"+{minutes}"])
    print(out or err or f"Shutdown scheduled in {minutes} minutes.")
    return rc


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: zorincare-root-helper <action> [json_payload]", file=sys.stderr)
        return 2

    action = sys.argv[1]
    raw_json = sys.argv[2] if len(sys.argv) >= 3 else "{}"
    try:
        payload = json.loads(raw_json) if raw_json else {}
    except Exception as exc:
        print(f"Invalid JSON payload: {exc}", file=sys.stderr)
        return 2

    dispatch = {
        "system_care_clean": lambda: handle_system_care_clean(payload),
        "drop_caches": handle_drop_caches,
        "apply_sysctl": lambda: handle_apply_sysctl(payload),
        "reset_sysctl": handle_reset_sysctl,
        "set_cpu_governor": lambda: handle_set_cpu_governor(payload),
        "install_drivers_auto": handle_install_drivers_auto,
        "apt_install": lambda: handle_apt_install(payload),
        "fwupd_update": handle_fwupd_update,
        "uninstall_pkg": lambda: handle_uninstall_pkg(payload),
        "delete_root_leftovers": lambda: handle_delete_root_leftovers(payload),
        "service_action": lambda: handle_service_action(payload),
        "ufw_action": lambda: handle_ufw_action(payload),
        "set_dns": lambda: handle_set_dns(payload),
        "power_schedule": lambda: handle_power_schedule(payload),
    }

    handler = dispatch.get(action)
    if not handler:
        print(f"Unknown helper action: {action}", file=sys.stderr)
        return 2
    return handler()


if __name__ == "__main__":
    raise SystemExit(main())
