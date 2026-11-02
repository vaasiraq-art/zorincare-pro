"""Security & Privacy Shield engine: UFW Firewall, Open Port Auditor, Browser/Activity Privacy Sweep & Hardening."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from zorincare.core.runner import LOG_BUS, run_cmd, run_privileged, which_bin


@dataclass
class ListeningPort:
    proto: str
    local_address: str
    port: str
    process_info: str


@dataclass
class PrivacyTarget:
    target_id: str
    title_key: str
    size_bytes: int
    items_count: int
    selected: bool


@dataclass
class SecurityAuditCheck:
    title: str
    passed: bool
    detail: str


def get_ufw_enabled_status() -> tuple[bool, bool, str]:
    """Return (installed, enabled, detail) without prompting for root password."""
    ufw_conf = Path("/etc/ufw/ufw.conf")
    installed = which_bin("ufw") is not None or ufw_conf.exists()
    if not installed:
        return False, False, "UFW package is not installed"

    if ufw_conf.exists():
        try:
            for line in ufw_conf.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip().startswith("ENABLED="):
                    val = line.split("=", 1)[1].strip().lower()
                    is_en = val == "yes"
                    return True, is_en, "Active (Default Deny Incoming)" if is_en else "Firewall Disabled"
        except OSError:
            pass
    return True, False, "Unknown / Inactive"


def set_ufw_state(enable: bool) -> tuple[bool, str]:
    op = "enable" if enable else "disable"
    res = run_privileged("ufw_action", {"op": op}, timeout=30)
    return res.ok, res.combined_output


def list_listening_ports() -> list[ListeningPort]:
    if not which_bin("ss"):
        return []
    res = run_cmd(["ss", "-tulnp"], timeout=10)
    if not res.ok:
        return []
    ports: list[ListeningPort] = []
    for line in res.stdout.splitlines()[1:]:
        cols = line.split()
        if len(cols) < 5:
            continue
        proto = cols[0].upper()
        local_addr = cols[4]
        port = local_addr.rsplit(":", 1)[-1] if ":" in local_addr else local_addr
        proc = cols[6] if len(cols) >= 7 else "system/kernel"
        ports.append(ListeningPort(proto=proto, local_address=local_addr, port=port, process_info=proc))
    return ports


def _browser_cache_paths(home: Path) -> list[Path]:
    return [
        # Native APT / .deb browser caches (Brave is default on Zorin OS!)
        home / ".cache" / "BraveSoftware" / "Brave-Browser",
        home / ".cache" / "mozilla" / "firefox",
        home / ".cache" / "google-chrome",
        home / ".cache" / "chromium",
        home / ".cache" / "microsoft-edge",
        home / ".cache" / "vivaldi",
        # Flatpak sandboxed browser caches
        home / ".var" / "app" / "com.brave.Browser" / "cache",
        home / ".var" / "app" / "org.mozilla.firefox" / "cache",
        home / ".var" / "app" / "com.google.Chrome" / "cache",
        home / ".var" / "app" / "org.chromium.Chromium" / "cache",
        home / ".var" / "app" / "com.microsoft.Edge" / "cache",
    ]


def _folder_bytes(p: Path) -> tuple[int, int]:
    if not p.exists():
        return 0, 0
    if p.is_file():
        try:
            return p.stat().st_size, 1
        except OSError:
            return 0, 0
    sz, cnt = 0, 0
    try:
        for root, _, files in os.walk(p, followlinks=False):
            for f in files:
                try:
                    sz += (Path(root) / f).stat().st_size
                    cnt += 1
                except OSError:
                    pass
    except OSError:
        pass
    return sz, cnt


def scan_privacy_traces() -> list[PrivacyTarget]:
    home = Path.home()

    # 1. Recent files
    recent_file = home / ".local" / "share" / "recently-used.xbel"
    r_sz, r_cnt = _folder_bytes(recent_file)

    # 2. Browser caches
    b_sz, b_cnt = 0, 0
    for bp in _browser_cache_paths(home):
        s, c = _folder_bytes(bp)
        b_sz += s
        b_cnt += c

    # 3. Thumbnails
    t_sz, t_cnt = _folder_bytes(home / ".cache" / "thumbnails")

    # 4. Shell history (opt-in: selected=False by default!)
    h_sz, h_cnt = 0, 0
    for hf in (home / ".bash_history", home / ".zsh_history"):
        s, c = _folder_bytes(hf)
        h_sz += s
        h_cnt += c

    return [
        PrivacyTarget("recent", "priv_recent", r_sz, r_cnt, selected=r_cnt > 0),
        PrivacyTarget("browsers", "priv_browsers", b_sz, b_cnt, selected=b_cnt > 0),
        PrivacyTarget("thumbnails", "priv_thumbnails", t_sz, t_cnt, selected=t_cnt > 0),
        PrivacyTarget("shell_hist", "priv_shell_hist", h_sz, h_cnt, selected=False),
    ]


def clean_privacy_traces(selected_ids: list[str]) -> int:
    home = Path.home()
    freed = 0

    def _wipe_dir(d: Path) -> int:
        if not d.exists():
            return 0
        s, _ = _folder_bytes(d)
        for child in d.iterdir():
            try:
                if child.is_symlink() or child.is_file():
                    child.unlink()
                elif child.is_dir():
                    shutil.rmtree(child)
            except OSError:
                pass
        return s

    if "recent" in selected_ids:
        rf = home / ".local" / "share" / "recently-used.xbel"
        if rf.exists():
            try:
                freed += rf.stat().st_size
                # Write valid empty XBEL skeleton so GNOME Files stays happy
                rf.write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n<xbel version="1.0"/>\n',
                    encoding="utf-8",
                )
            except OSError:
                pass

    if "browsers" in selected_ids:
        for bp in _browser_cache_paths(home):
            freed += _wipe_dir(bp)

    if "thumbnails" in selected_ids:
        freed += _wipe_dir(home / ".cache" / "thumbnails")

    if "shell_hist" in selected_ids:
        for hf in (home / ".bash_history", home / ".zsh_history"):
            if hf.exists():
                try:
                    freed += hf.stat().st_size
                    hf.write_text("", encoding="utf-8")
                except OSError:
                    pass

    LOG_BUS.emit(f"Privacy sweep freed {freed} bytes across {', '.join(selected_ids)}")
    return freed


def run_security_audit() -> list[SecurityAuditCheck]:
    checks: list[SecurityAuditCheck] = []

    # 1. UFW status
    inst, en, detail = get_ufw_enabled_status()
    checks.append(
        SecurityAuditCheck(
            title="UFW System Firewall",
            passed=bool(inst and en),
            detail=detail,
        )
    )

    # 2. ~/.ssh directory permissions
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        checks.append(SecurityAuditCheck("SSH Key Permissions (~/.ssh)", True, "No ~/.ssh folder present"))
    else:
        mode = ssh_dir.stat().st_mode & 0o777
        ok_perm = (mode & 0o077) == 0
        checks.append(
            SecurityAuditCheck(
                "SSH Key Permissions (~/.ssh)",
                ok_perm,
                f"Mode {oct(mode)} ({'Secure 700' if ok_perm else 'Too open — should be 0700'})",
            )
        )

    # 3. Automatic APT security updates
    auto_upg = Path("/etc/apt/apt.conf.d/20auto-upgrades")
    auto_ok = False
    if auto_upg.exists():
        txt = auto_upg.read_text(encoding="utf-8", errors="ignore")
        auto_ok = 'Unattended-Upgrade "1"' in txt
    checks.append(
        SecurityAuditCheck(
            "Automatic Security Updates",
            auto_ok,
            "Enabled via unattended-upgrades" if auto_ok else "Manual updates configured",
        )
    )

    return checks
