"""Turbo Boost & Kernel Performance Optimizer for Zorin OS 18.1 Pro."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from zorincare import get_config_dir
from zorincare.core.runner import LOG_BUS, run_cmd, run_privileged, which_bin


@dataclass
class MemorySnapshot:
    total_bytes: int
    used_bytes: int
    available_bytes: int
    cached_bytes: int
    swap_total_bytes: int
    swap_used_bytes: int

    @property
    def used_percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return round((self.used_bytes / self.total_bytes) * 100.0, 1)

    @property
    def swap_percent(self) -> float:
        if self.swap_total_bytes <= 0:
            return 0.0
        return round((self.swap_used_bytes / self.swap_total_bytes) * 100.0, 1)


@dataclass
class KernelTweakSpec:
    tweak_id: str
    title_key: str
    desc_key: str
    sysctl_pairs: dict[str, str]
    proc_check_path: str
    recommended_display: str


KERNEL_TWEAKS: list[KernelTweakSpec] = [
    KernelTweakSpec(
        tweak_id="swappiness",
        title_key="tweak_swappiness",
        desc_key="tweak_swappiness_desc",
        sysctl_pairs={"vm.swappiness": "10"},
        proc_check_path="/proc/sys/vm/swappiness",
        recommended_display="10",
    ),
    KernelTweakSpec(
        tweak_id="vfs",
        title_key="tweak_vfs",
        desc_key="tweak_vfs_desc",
        sysctl_pairs={"vm.vfs_cache_pressure": "50"},
        proc_check_path="/proc/sys/vm/vfs_cache_pressure",
        recommended_display="50",
    ),
    KernelTweakSpec(
        tweak_id="dirty",
        title_key="tweak_dirty",
        desc_key="tweak_dirty_desc",
        sysctl_pairs={"vm.dirty_ratio": "15", "vm.dirty_background_ratio": "5"},
        proc_check_path="/proc/sys/vm/dirty_ratio",
        recommended_display="15 / 5",
    ),
    KernelTweakSpec(
        tweak_id="bbr",
        title_key="tweak_bbr",
        desc_key="tweak_bbr_desc",
        sysctl_pairs={"net.core.default_qdisc": "fq", "net.ipv4.tcp_congestion_control": "bbr"},
        proc_check_path="/proc/sys/net/ipv4/tcp_congestion_control",
        recommended_display="bbr",
    ),
    KernelTweakSpec(
        tweak_id="mapcount",
        title_key="tweak_mapcount",
        desc_key="tweak_mapcount_desc",
        sysctl_pairs={"vm.max_map_count": "2147483642"},
        proc_check_path="/proc/sys/vm/max_map_count",
        recommended_display="2147483642",
    ),
]


def read_memory_snapshot() -> MemorySnapshot:
    meminfo = Path("/proc/meminfo")
    vals: dict[str, int] = {}
    if meminfo.exists():
        try:
            for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
                if ":" in line:
                    k, rest = line.split(":", 1)
                    parts = rest.strip().split()
                    if parts and parts[0].isdigit():
                        vals[k.strip()] = int(parts[0]) * 1024
        except OSError:
            pass

    if not vals:
        # Non-Linux preview fallback
        total = 16 * 1024**3
        avail = 9 * 1024**3
        return MemorySnapshot(total, total - avail, avail, 3 * 1024**3, 4 * 1024**3, 256 * 1024**2)

    total = vals.get("MemTotal", 0)
    avail = vals.get("MemAvailable", vals.get("MemFree", 0))
    cached = vals.get("Cached", 0) + vals.get("Buffers", 0) + vals.get("SReclaimable", 0)
    used = max(0, total - avail)
    swap_total = vals.get("SwapTotal", 0)
    swap_free = vals.get("SwapFree", 0)
    swap_used = max(0, swap_total - swap_free)
    return MemorySnapshot(total, used, avail, cached, swap_total, swap_used)


def boost_ram_memory() -> tuple[bool, int, str]:
    """Flush clean kernel caches and return (ok, freed_bytes, message)."""
    before = read_memory_snapshot()
    res = run_privileged("drop_caches", {}, timeout=60)
    if not res.ok:
        return False, 0, res.combined_output
    after = read_memory_snapshot()
    freed = max(0, after.available_bytes - before.available_bytes)
    LOG_BUS.emit(f"RAM Boost freed {freed} bytes")
    return True, freed, res.combined_output


def get_active_power_profile() -> str:
    if which_bin("powerprofilesctl"):
        out = run_cmd(["powerprofilesctl", "get"], timeout=10)
        if out.ok and out.stdout.strip():
            return out.stdout.strip()
    gov_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    if gov_path.exists():
        try:
            gov = gov_path.read_text(encoding="utf-8").strip()
            if gov == "performance":
                return "performance"
            if gov == "powersave":
                return "power-saver"
        except OSError:
            pass
    return "balanced"


def set_power_profile(profile: str) -> tuple[bool, str]:
    """Set profile: 'performance', 'balanced', or 'power-saver'."""
    if which_bin("powerprofilesctl"):
        res = run_cmd(["powerprofilesctl", "set", profile], timeout=15, log=True)
        if res.ok:
            return True, f"Power profile set to {profile}."
    gov_map = {
        "performance": "performance",
        "balanced": "schedutil",
        "power-saver": "powersave",
    }
    gov = gov_map.get(profile, "schedutil")
    res = run_privileged("set_cpu_governor", {"governor": gov}, timeout=30)
    return res.ok, res.combined_output


def apply_turbo_mode(mode: str) -> tuple[bool, str]:
    """Apply 'game', 'work', 'saver', or 'normal' boost profile."""
    state_file = get_config_dir() / "boost_state.json"

    if mode == "normal":
        ok, msg = set_power_profile("balanced")
        if which_bin("systemctl"):
            run_cmd(["systemctl", "--user", "start", "tracker-miner-fs-3.service"], timeout=10)
        state_file.write_text(json.dumps({"active_mode": "normal"}), encoding="utf-8")
        return ok, msg

    if mode == "game":
        ok, msg = set_power_profile("performance")
        # Pause heavy background file indexer while gaming
        if which_bin("systemctl"):
            run_cmd(["systemctl", "--user", "stop", "tracker-miner-fs-3.service"], timeout=10)
        boost_ram_memory()
        state_file.write_text(json.dumps({"active_mode": "game"}), encoding="utf-8")
        return ok, msg

    if mode == "work":
        ok, msg = set_power_profile("performance")
        state_file.write_text(json.dumps({"active_mode": "work"}), encoding="utf-8")
        return ok, msg

    if mode == "saver":
        ok, msg = set_power_profile("power-saver")
        state_file.write_text(json.dumps({"active_mode": "saver"}), encoding="utf-8")
        return ok, msg

    return False, f"Unknown mode: {mode}"


def get_current_turbo_mode() -> str:
    state_file = get_config_dir() / "boost_state.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return str(data.get("active_mode", "normal"))
        except Exception:
            pass
    return "normal"


def get_kernel_tweak_states() -> list[tuple[KernelTweakSpec, str, bool]]:
    """Return (spec, current_value, is_active) for each Zorin kernel tweak."""
    results: list[tuple[KernelTweakSpec, str, bool]] = []
    for spec in KERNEL_TWEAKS:
        p = Path(spec.proc_check_path)
        cur = "default"
        if p.exists():
            try:
                cur = p.read_text(encoding="utf-8").strip()
            except OSError:
                pass
        first_target = next(iter(spec.sysctl_pairs.values()))
        # Check if first target matches current
        if spec.tweak_id == "dirty":
            is_active = cur == "15"
        else:
            is_active = cur == first_target
        results.append((spec, cur, is_active))
    return results


def apply_selected_kernel_tweaks(selected_ids: list[str]) -> tuple[bool, str]:
    merged: dict[str, str] = {}
    for spec in KERNEL_TWEAKS:
        if spec.tweak_id in selected_ids:
            merged.update(spec.sysctl_pairs)
    if not merged:
        res = run_privileged("reset_sysctl", {}, timeout=45)
        return res.ok, res.combined_output
    res = run_privileged("apply_sysctl", {"settings": merged}, timeout=60)
    return res.ok, res.combined_output


def reset_kernel_tweaks() -> tuple[bool, str]:
    res = run_privileged("reset_sysctl", {}, timeout=45)
    return res.ok, res.combined_output
