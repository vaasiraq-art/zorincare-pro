"""Full PC Control Center engine: telemetry, process killer, startup/services, DNS, power, Zorin tweaks & disk analyzer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import configparser
import os
import shutil
import signal
import time

from zorincare.core.runner import LOG_BUS, run_cmd, run_privileged, which_bin
from zorincare.core.turbo_boost import MemorySnapshot, read_memory_snapshot


PROTECTED_PROC_NAMES = {
    "systemd",
    "init",
    "kthreadd",
    "gnome-shell",
    "gdm3",
    "gdm-wayland-session",
    "Xorg",
    "Xwayland",
    "dbus-daemon",
    "polkitd",
    "zorincare-pro",
}


@dataclass
class TelemetrySample:
    cpu_percent: float
    cpu_freq_mhz: int
    temp_celsius: float | None
    memory: MemorySnapshot
    net_down_bps: float
    net_up_bps: float
    root_used_bytes: int
    root_total_bytes: int
    uptime_seconds: int
    battery_percent: int | None
    battery_charging: bool


@dataclass
class ProcessInfo:
    pid: int
    user: str
    cpu_percent: float
    ram_bytes: int
    state: str
    name: str

    @property
    def protected(self) -> bool:
        return self.pid <= 2 or self.name in PROTECTED_PROC_NAMES


@dataclass
class AutostartItem:
    name: str
    comment: str
    exec_cmd: str
    enabled: bool
    file_path: Path
    is_system_origin: bool


@dataclass
class SystemdServiceItem:
    unit: str
    load_state: str
    active_state: str
    sub_state: str
    description: str


@dataclass
class ZorinDesktopTweak:
    tweak_id: str
    title_key: str
    schema: str
    key: str
    enabled: bool
    available: bool


@dataclass
class DiskSpaceItem:
    path: str
    size_bytes: int
    is_dir: bool


class LiveTelemetryPoller:
    """Zero-dependency Linux /proc & /sys live hardware monitor."""

    def __init__(self) -> None:
        self._prev_cpu_total = 0
        self._prev_cpu_idle = 0
        self._prev_net_rx = 0
        self._prev_net_tx = 0
        self._prev_net_time = 0.0
        # Prime initial counters
        self._read_cpu_jiffies()
        self._read_net_bytes()
        self._prev_net_time = time.monotonic()

    def _read_cpu_jiffies(self) -> tuple[int, int]:
        stat_path = Path("/proc/stat")
        if not stat_path.exists():
            return 0, 0
        try:
            first = stat_path.read_text(encoding="utf-8").splitlines()[0]
            nums = [int(x) for x in first.split()[1:]]
            idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
            total = sum(nums)
            return total, idle
        except Exception:
            return 0, 0

    def _read_net_bytes(self) -> tuple[int, int]:
        net_path = Path("/proc/net/dev")
        if not net_path.exists():
            return 0, 0
        rx_sum, tx_sum = 0, 0
        try:
            for line in net_path.read_text(encoding="utf-8").splitlines()[2:]:
                if ":" not in line:
                    continue
                iface, rest = line.split(":", 1)
                iface = iface.strip()
                if iface == "lo":
                    continue
                cols = rest.split()
                if len(cols) >= 9:
                    rx_sum += int(cols[0])
                    tx_sum += int(cols[8])
        except Exception:
            pass
        return rx_sum, tx_sum

    def _read_cpu_freq_mhz(self) -> int:
        freq_file = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
        if freq_file.exists():
            try:
                khz = int(freq_file.read_text(encoding="utf-8").strip())
                return khz // 1000
            except Exception:
                pass
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            try:
                for line in cpuinfo.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if "cpu mhz" in line.lower() and ":" in line:
                        return int(float(line.split(":", 1)[1].strip()))
            except Exception:
                pass
        return 0

    def _read_temperature(self) -> float | None:
        temps: list[float] = []
        hwmon_root = Path("/sys/class/hwmon")
        if hwmon_root.exists():
            for tf in hwmon_root.glob("hwmon*/temp*_input"):
                try:
                    milli = int(tf.read_text(encoding="utf-8").strip())
                    c = milli / 1000.0
                    if 10.0 <= c <= 125.0:
                        temps.append(c)
                except Exception:
                    pass
        if not temps:
            tz_root = Path("/sys/class/thermal")
            if tz_root.exists():
                for tf in tz_root.glob("thermal_zone*/temp"):
                    try:
                        milli = int(tf.read_text(encoding="utf-8").strip())
                        c = milli / 1000.0 if milli > 200 else float(milli)
                        if 10.0 <= c <= 125.0:
                            temps.append(c)
                    except Exception:
                        pass
        return round(max(temps), 1) if temps else None

    def _read_uptime(self) -> int:
        up_file = Path("/proc/uptime")
        if up_file.exists():
            try:
                return int(float(up_file.read_text(encoding="utf-8").split()[0]))
            except Exception:
                pass
        return 0

    def _read_battery(self) -> tuple[int | None, bool]:
        ps_root = Path("/sys/class/power_supply")
        if ps_root.exists():
            for bat in ps_root.glob("BAT*"):
                cap_file = bat / "capacity"
                stat_file = bat / "status"
                try:
                    pct = int(cap_file.read_text(encoding="utf-8").strip())
                    st = stat_file.read_text(encoding="utf-8").strip().lower() if stat_file.exists() else ""
                    return pct, st in ("charging", "full")
                except Exception:
                    pass
        return None, False

    def sample(self) -> TelemetrySample:
        # CPU %
        cur_total, cur_idle = self._read_cpu_jiffies()
        dt_total = cur_total - self._prev_cpu_total
        dt_idle = cur_idle - self._prev_cpu_idle
        self._prev_cpu_total, self._prev_cpu_idle = cur_total, cur_idle
        cpu_pct = 0.0
        if dt_total > 0:
            cpu_pct = round(max(0.0, min(100.0, (1.0 - dt_idle / dt_total) * 100.0)), 1)

        # Network B/s
        now = time.monotonic()
        rx, tx = self._read_net_bytes()
        elapsed = max(0.2, now - self._prev_net_time)
        down_bps = max(0.0, (rx - self._prev_net_rx) / elapsed) if self._prev_net_rx > 0 else 0.0
        up_bps = max(0.0, (tx - self._prev_net_tx) / elapsed) if self._prev_net_tx > 0 else 0.0
        self._prev_net_rx, self._prev_net_tx, self._prev_net_time = rx, tx, now

        # Disk root
        try:
            du = shutil.disk_usage("/")
            root_used, root_total = du.used, du.total
        except Exception:
            root_used, root_total = 0, 1

        bat_pct, bat_chg = self._read_battery()

        return TelemetrySample(
            cpu_percent=cpu_pct,
            cpu_freq_mhz=self._read_cpu_freq_mhz(),
            temp_celsius=self._read_temperature(),
            memory=read_memory_snapshot(),
            net_down_bps=down_bps,
            net_up_bps=up_bps,
            root_used_bytes=root_used,
            root_total_bytes=root_total,
            uptime_seconds=self._read_uptime(),
            battery_percent=bat_pct,
            battery_charging=bat_chg,
        )


def list_processes(limit: int = 80) -> list[ProcessInfo]:
    if not which_bin("ps"):
        return []
    res = run_cmd(
        ["ps", "-eo", "pid=,user=,pcpu=,rss=,stat=,comm=", "--sort=-pcpu"],
        timeout=10,
    )
    if not res.ok:
        return []
    procs: list[ProcessInfo] = []
    for line in res.stdout.splitlines():
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        try:
            pid = int(parts[0])
            user = parts[1]
            cpu = float(parts[2])
            rss_bytes = int(parts[3]) * 1024
            stat = parts[4]
            comm = parts[5].strip()
            procs.append(ProcessInfo(pid, user, cpu, rss_bytes, stat, comm))
            if len(procs) >= limit:
                break
        except ValueError:
            continue
    return procs


def terminate_process(pid: int, name: str = "", force: bool = False) -> tuple[bool, str]:
    if pid <= 2 or name in PROTECTED_PROC_NAMES:
        return False, f"Refusing to terminate protected desktop/system process ({name or pid})."
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.kill(pid, sig)
        LOG_BUS.emit(f"Sent {'SIGKILL' if force else 'SIGTERM'} to PID {pid} ({name})")
        return True, f"Terminated PID {pid}."
    except PermissionError:
        return False, "Permission denied (process owned by another user/root)."
    except ProcessLookupError:
        return True, "Process already exited."
    except Exception as exc:
        return False, str(exc)


def list_autostart_entries() -> list[AutostartItem]:
    user_dir = Path.home() / ".config" / "autostart"
    sys_dir = Path("/etc/xdg/autostart")
    merged: dict[str, tuple[Path, bool]] = {}

    if sys_dir.exists():
        for f in sys_dir.glob("*.desktop"):
            merged[f.name] = (f, True)
    if user_dir.exists():
        for f in user_dir.glob("*.desktop"):
            merged[f.name] = (f, False)

    items: list[AutostartItem] = []
    for fname, (fpath, is_sys) in sorted(merged.items()):
        cp = configparser.ConfigParser(interpolation=None)
        try:
            cp.read(fpath, encoding="utf-8")
            sec = cp["Desktop Entry"]
        except Exception:
            continue
        if sec.get("NoDisplay", "false").lower() == "true":
            continue
        hidden = sec.get("Hidden", "false").lower() == "true"
        gnome_en = sec.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
        enabled = (not hidden) and gnome_en
        items.append(
            AutostartItem(
                name=sec.get("Name", fname).strip(),
                comment=sec.get("Comment", "").strip(),
                exec_cmd=sec.get("Exec", "").strip(),
                enabled=enabled,
                file_path=fpath,
                is_system_origin=is_sys,
            )
        )
    items.sort(key=lambda x: x.name.lower())
    return items


def set_autostart_enabled(item: AutostartItem, enabled: bool) -> bool:
    user_dir = Path.home() / ".config" / "autostart"
    user_dir.mkdir(parents=True, exist_ok=True)
    target = user_dir / item.file_path.name
    if item.is_system_origin and not target.exists():
        try:
            shutil.copy2(item.file_path, target)
        except OSError:
            return False

    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str  # preserve case of Desktop Entry keys!
    try:
        cp.read(target, encoding="utf-8")
        if "Desktop Entry" not in cp:
            return False
        cp["Desktop Entry"]["X-GNOME-Autostart-enabled"] = "true" if enabled else "false"
        cp["Desktop Entry"]["Hidden"] = "false" if enabled else "true"
        with target.open("w", encoding="utf-8") as fh:
            cp.write(fh, space_around_delimiters=False)
        LOG_BUS.emit(f"Autostart '{item.name}' -> enabled={enabled}")
        return True
    except Exception:
        return False


def list_systemd_services(limit: int = 80) -> list[SystemdServiceItem]:
    if not which_bin("systemctl"):
        return []
    res = run_cmd(
        ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"],
        timeout=15,
    )
    if not res.ok:
        return []
    items: list[SystemdServiceItem] = []
    for raw_line in res.stdout.splitlines():
        line = raw_line.lstrip("●* ").strip()
        parts = line.split(None, 4)
        if len(parts) >= 5:
            items.append(
                SystemdServiceItem(
                    unit=parts[0],
                    load_state=parts[1],
                    active_state=parts[2],
                    sub_state=parts[3],
                    description=parts[4],
                )
            )
            if len(items) >= limit:
                break
    return items


def control_systemd_service(unit: str, op: str) -> tuple[bool, str]:
    res = run_privileged("service_action", {"unit": unit, "op": op}, timeout=60)
    return res.ok, res.combined_output


def switch_dns_preset(preset: str) -> tuple[bool, str]:
    res = run_privileged("set_dns", {"preset": preset}, timeout=45)
    return res.ok, res.combined_output


def flush_dns_cache() -> tuple[bool, str]:
    if which_bin("resolvectl"):
        res = run_cmd(["resolvectl", "flush-caches"], timeout=10, log=True)
        if res.ok:
            return True, "DNS cache flushed."
    res = run_privileged("set_dns", {"preset": "auto"}, timeout=30)
    return res.ok, res.combined_output


def schedule_power_shutdown(minutes: int | None) -> tuple[bool, str]:
    if minutes is None:
        res = run_privileged("power_schedule", {"op": "cancel"}, timeout=15)
    else:
        res = run_privileged("power_schedule", {"op": "schedule", "minutes": minutes}, timeout=15)
    return res.ok, res.combined_output


ZORIN_TWEAK_DEFS = [
    ("battery_pct", "ctrl_tweak_battery_pct", "org.gnome.desktop.interface", "show-battery-percentage"),
    ("night_light", "ctrl_tweak_night_light", "org.gnome.settings-daemon.plugins.color", "night-light-enabled"),
    ("animations", "ctrl_tweak_animations", "org.gnome.desktop.interface", "enable-animations"),
    ("center_win", "ctrl_tweak_center_win", "org.gnome.mutter", "center-new-windows"),
    ("tap_click", "ctrl_tweak_tap_click", "org.gnome.desktop.peripherals.touchpad", "tap-to-click"),
]


def get_zorin_desktop_tweaks() -> list[ZorinDesktopTweak]:
    has_gs = which_bin("gsettings") is not None
    tweaks: list[ZorinDesktopTweak] = []
    for tid, tkey, schema, gkey in ZORIN_TWEAK_DEFS:
        if not has_gs:
            tweaks.append(ZorinDesktopTweak(tid, tkey, schema, gkey, False, False))
            continue
        res = run_cmd(["gsettings", "get", schema, gkey], timeout=5)
        if res.ok:
            val = res.stdout.strip().lower() == "true"
            tweaks.append(ZorinDesktopTweak(tid, tkey, schema, gkey, val, True))
        else:
            tweaks.append(ZorinDesktopTweak(tid, tkey, schema, gkey, False, False))
    return tweaks


def set_zorin_desktop_tweak(schema: str, key: str, enabled: bool) -> bool:
    if not which_bin("gsettings"):
        return False
    val_str = "true" if enabled else "false"
    res = run_cmd(["gsettings", "set", schema, key, val_str], timeout=8, log=True)
    return res.ok


def analyze_home_disk_space(target_dir: Path | None = None, top_n: int = 25) -> list[DiskSpaceItem]:
    """Scan top-level directories in ~/ to reveal biggest disk space consumers."""
    base = target_dir or Path.home()
    LOG_BUS.emit(f"Analyzing disk usage in {base}...")
    if which_bin("du"):
        res = run_cmd(["du", "-B1", "--max-depth=1", str(base)], timeout=60)
        if res.ok:
            items: list[DiskSpaceItem] = []
            for line in res.stdout.splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2 and parts[0].strip().isdigit():
                    sz = int(parts[0].strip())
                    p = Path(parts[1].strip())
                    if p.resolve() == base.resolve():
                        continue
                    items.append(DiskSpaceItem(str(p), sz, p.is_dir()))
            items.sort(key=lambda x: -x.size_bytes)
            return items[:top_n]

    # Pure Python fallback
    items = []
    try:
        for child in base.iterdir():
            if child.is_symlink():
                continue
            if child.is_file():
                try:
                    items.append(DiskSpaceItem(str(child), child.stat().st_size, False))
                except OSError:
                    pass
            elif child.is_dir():
                total = 0
                try:
                    for root, _, files in os.walk(child, followlinks=False):
                        for fn in files:
                            try:
                                total += (Path(root) / fn).stat().st_size
                            except OSError:
                                pass
                except OSError:
                    pass
                items.append(DiskSpaceItem(str(child), total, True))
    except OSError:
        pass
    items.sort(key=lambda x: -x.size_bytes)
    return items[:top_n]
