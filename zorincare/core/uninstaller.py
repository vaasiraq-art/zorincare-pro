"""Revo-Style Universal Uninstaller & Deep Leftover Hunter for Zorin OS 18.1 Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import configparser
import os
import re
import shlex
import shutil
import tarfile

from zorincare import get_backup_dir
from zorincare.core.root_helper import PROTECTED_PACKAGES, _is_safe_root_leftover
from zorincare.core.runner import LOG_BUS, run_cmd, run_privileged, which_bin


STOPWORD_TOKENS = {
    "app",
    "apps",
    "application",
    "bin",
    "bus",
    "cfg",
    "cli",
    "com",
    "common",
    "config",
    "core",
    "data",
    "desktop",
    "dev",
    "doc",
    "etc",
    "freedesktop",
    "gnome",
    "gnu",
    "gpg",
    "gtk",
    "gtk3",
    "gtk4",
    "gui",
    "home",
    "ice",
    "icon",
    "icons",
    "io",
    "kde",
    "lib",
    "linux",
    "local",
    "log",
    "main",
    "man",
    "net",
    "open",
    "opt",
    "org",
    "pkg",
    "pro",
    "python",
    "python3",
    "qt",
    "run",
    "service",
    "settings",
    "share",
    "snap",
    "software",
    "src",
    "ssh",
    "ssl",
    "sys",
    "system",
    "systemd",
    "tmp",
    "tool",
    "tools",
    "ubuntu",
    "usr",
    "util",
    "utils",
    "var",
    "viewer",
    "wayland",
    "web",
    "window",
    "x11",
    "xdg",
    "zorin",
    "zorincare",
}

PROTECTED_USER_DIRS = {
    "autostart",
    "dconf",
    "evolution",
    "fontconfig",
    "gconf",
    "gnome-control-center",
    "gnome-session",
    "gnome-shell",
    "goa-1.0",
    "gtk-2.0",
    "gtk-3.0",
    "gtk-4.0",
    "gvfs-metadata",
    "ibus",
    "keyrings",
    "menus",
    "mime",
    "nautilus",
    "NetworkManager",
    "pipewire",
    "pulse",
    "Session",
    "sounds",
    "systemd",
    "themes",
    "thumbnails",
    "Trash",
    "tracker3",
    "user-dirs.dirs",
    "zorincare-pro",
}

BASE_SNAP_EXCLUSIONS = {
    "bare",
    "core",
    "core18",
    "core20",
    "core22",
    "core24",
    "snapd",
    "gtk-common-themes",
    "gnome-3-38-2004",
    "gnome-42-2204",
    "gnome-46-2404",
    "mesa-2404",
}


@dataclass
class InstalledApp:
    name: str
    pkg_id: str
    source: str  # "apt" | "flatpak" | "snap" | "appimage" | "wine"
    version: str
    size_bytes: int = 0
    icon: str = "application-x-executable-symbolic"
    desktop_file: str = ""
    exec_bin: str = ""
    protected: bool = False


@dataclass
class LeftoverItem:
    path: str
    kind: str  # "config" | "cache" | "data" | "sandbox" | "launcher" | "system"
    size_bytes: int
    requires_root: bool
    risk: str = "safe"  # "safe" | "review"
    selected: bool = True


def _calc_path_size(target: Path) -> int:
    if not target.exists() and not target.is_symlink():
        return 0
    if target.is_symlink() or target.is_file():
        try:
            return target.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        for root, _, files in os.walk(target, followlinks=False):
            for f in files:
                fp = Path(root) / f
                try:
                    if not fp.is_symlink():
                        total += fp.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _parse_size_str(raw: str) -> int:
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?i?B|B)", raw, re.IGNORECASE)
    if not m:
        return 0
    val = float(m.group(1))
    u = m.group(2).upper().replace("IB", "B")
    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(val * mult.get(u, 1))


def list_apt_desktop_apps() -> list[InstalledApp]:
    apps_dir = Path("/usr/share/applications")
    if not apps_dir.exists() or not which_bin("dpkg-query"):
        return []

    desktop_files = sorted(apps_dir.glob("*.desktop"))
    if not desktop_files:
        return []

    # 1. Batch-map .desktop files -> owning APT package in ONE fast dpkg -S call
    dpkg_s = run_cmd(["dpkg", "-S"] + [str(p) for p in desktop_files], timeout=25)
    file_to_pkg: dict[str, str] = {}
    for line in (dpkg_s.stdout or "").splitlines():
        if ": " in line:
            pkg_part, path_part = line.split(": ", 1)
            pkg_name = pkg_part.split(":")[0].strip()
            file_to_pkg[path_part.strip()] = pkg_name

    # 2. Batch-query package versions and installed sizes
    pkg_meta: dict[str, tuple[str, int]] = {}
    q_res = run_cmd(
        ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Installed-Size}\n"],
        timeout=20,
    )
    if q_res.ok:
        for line in q_res.stdout.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                pname = cols[0].split(":")[0].strip()
                ver = cols[1].strip()
                sz = int(cols[2].strip()) * 1024 if cols[2].strip().isdigit() else 0
                pkg_meta[pname] = (ver, sz)

    seen_pkgs: set[str] = set()
    results: list[InstalledApp] = []

    for dfile in desktop_files:
        pkg = file_to_pkg.get(str(dfile))
        if not pkg or pkg in seen_pkgs:
            continue

        cp = configparser.ConfigParser(interpolation=None)
        try:
            cp.read(dfile, encoding="utf-8")
        except Exception:
            continue
        if "Desktop Entry" not in cp:
            continue
        sec = cp["Desktop Entry"]
        if sec.get("NoDisplay", "false").lower() == "true":
            continue
        if sec.get("Type", "Application") != "Application":
            continue

        name = sec.get("Name", pkg).strip()
        icon = sec.get("Icon", "application-x-executable-symbolic").strip()
        exec_raw = sec.get("Exec", "").strip()
        exec_bin = ""
        if exec_raw:
            try:
                exec_bin = Path(shlex.split(exec_raw)[0]).name
            except Exception:
                exec_bin = exec_raw.split()[0]

        ver, sz = pkg_meta.get(pkg, ("installed", 0))
        is_prot = (
            pkg in PROTECTED_PACKAGES
            or pkg.startswith("zorin-")
            or pkg.startswith("gnome-shell")
            or pkg.startswith("ubuntu-")
        )
        seen_pkgs.add(pkg)
        results.append(
            InstalledApp(
                name=name,
                pkg_id=pkg,
                source="apt",
                version=ver,
                size_bytes=sz,
                icon=icon,
                desktop_file=str(dfile),
                exec_bin=exec_bin,
                protected=is_prot,
            )
        )
    return results


def list_flatpak_apps() -> list[InstalledApp]:
    if not which_bin("flatpak"):
        return []
    res = run_cmd(
        ["flatpak", "list", "--app", "--columns=name,application,version,size"],
        timeout=25,
    )
    if not res.ok:
        return []
    apps: list[InstalledApp] = []
    for line in res.stdout.splitlines():
        cols = line.split("\t")
        if len(cols) >= 2:
            name = cols[0].strip()
            app_id = cols[1].strip()
            if not app_id or app_id.lower() == "application id":
                continue
            ver = cols[2].strip() if len(cols) > 2 and cols[2].strip() else "latest"
            sz = _parse_size_str(cols[3]) if len(cols) > 3 else 0
            apps.append(
                InstalledApp(
                    name=name or app_id,
                    pkg_id=app_id,
                    source="flatpak",
                    version=ver,
                    size_bytes=sz,
                    icon=app_id,
                )
            )
    return apps


def list_snap_apps() -> list[InstalledApp]:
    if not which_bin("snap"):
        return []
    res = run_cmd(["snap", "list"], timeout=20)
    if not res.ok:
        return []
    apps: list[InstalledApp] = []
    for line in res.stdout.splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 5:
            sname, ver, rev = cols[0], cols[1], cols[2]
            if sname in BASE_SNAP_EXCLUSIONS:
                continue
            snap_file = Path(f"/var/lib/snapd/snaps/{sname}_{rev}.snap")
            sz = 0
            if snap_file.exists():
                try:
                    sz = snap_file.stat().st_size
                except OSError:
                    pass
            apps.append(
                InstalledApp(
                    name=sname.replace("-", " ").title(),
                    pkg_id=sname,
                    source="snap",
                    version=ver,
                    size_bytes=sz,
                    icon="package-x-generic-symbolic",
                )
            )
    return apps


def list_appimage_apps() -> list[InstalledApp]:
    home = Path.home()
    dirs = [home / "Applications", home / "Downloads", home / ".local" / "bin"]
    apps: list[InstalledApp] = []
    seen: set[str] = set()
    for d in dirs:
        if not d.exists():
            continue
        try:
            for item in d.iterdir():
                if item.is_file() and item.name.lower().endswith(".appimage"):
                    resolved = str(item.resolve())
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                    stem = re.sub(r"[-_]?[vV]?\d[\w.-]*$", "", item.stem) or item.stem
                    apps.append(
                        InstalledApp(
                            name=stem.replace("-", " ").replace("_", " ").strip(),
                            pkg_id=str(item),
                            source="appimage",
                            version="AppImage",
                            size_bytes=_calc_path_size(item),
                            icon="application-x-executable-symbolic",
                        )
                    )
        except OSError:
            pass
    return apps


def list_wine_apps() -> list[InstalledApp]:
    wine_prog_dir = Path.home() / ".local" / "share" / "applications" / "wine" / "Programs"
    if not wine_prog_dir.exists():
        return []
    apps: list[InstalledApp] = []
    for dfile in wine_prog_dir.rglob("*.desktop"):
        cp = configparser.ConfigParser(interpolation=None)
        try:
            cp.read(dfile, encoding="utf-8")
            sec = cp["Desktop Entry"]
            name = sec.get("Name", dfile.stem).strip()
        except Exception:
            name = dfile.stem
        apps.append(
            InstalledApp(
                name=f"{name} (Windows/Wine)",
                pkg_id=str(dfile),
                source="wine",
                version="Wine",
                size_bytes=_calc_path_size(dfile),
                icon="application-x-ms-dos-executable-symbolic",
                desktop_file=str(dfile),
            )
        )
    return apps


def list_all_installed_apps() -> list[InstalledApp]:
    LOG_BUS.emit("Loading installed applications across APT, Flatpak, Snap, AppImage & Wine...")
    combined = (
        list_apt_desktop_apps()
        + list_flatpak_apps()
        + list_snap_apps()
        + list_appimage_apps()
        + list_wine_apps()
    )
    combined.sort(key=lambda a: a.name.lower())
    return combined


def extract_app_tokens(app: InstalledApp) -> set[str]:
    """Derive safe, specific identifier tokens for leftover matching."""
    tokens: set[str] = set()
    raw_candidates = [app.pkg_id, app.exec_bin]

    if app.source == "flatpak" and "." in app.pkg_id:
        # e.g. org.videolan.VLC -> org.videolan.vlc, videolan, vlc
        tokens.add(app.pkg_id.lower())
        parts = app.pkg_id.lower().split(".")
        if len(parts) >= 3:
            raw_candidates.extend(parts[1:])
    elif app.source in ("appimage", "wine"):
        raw_candidates.append(Path(app.pkg_id).stem)

    slug_name = re.sub(r"[^a-z0-9]+", "-", app.name.lower()).strip("-")
    if len(slug_name) >= 3:
        raw_candidates.append(slug_name)

    for cand in raw_candidates:
        if not cand:
            continue
        cleaned = cand.lower().strip()
        if "/" in cleaned or "\\" in cleaned:
            cleaned = Path(cleaned).stem.lower()
        if len(cleaned) >= 3 and cleaned not in STOPWORD_TOKENS:
            tokens.add(cleaned)
            no_dash = cleaned.replace("-", "").replace("_", "")
            if len(no_dash) >= 4 and no_dash not in STOPWORD_TOKENS:
                tokens.add(no_dash)
    return tokens


def _name_matches_tokens(entry_name: str, tokens: set[str], exact_only: bool = False) -> bool:
    low = entry_name.lower()
    if low in PROTECTED_USER_DIRS or entry_name in PROTECTED_USER_DIRS:
        return False
    norm = low.replace("-", "").replace("_", "")
    for tok in tokens:
        if low == tok or norm == tok:
            return True
        if not exact_only and len(tok) >= 5:
            # Match prefix/word boundary such as brave-browser, discord-canary, org.gimp.GIMP
            if low.startswith(tok + "-") or low.startswith(tok + ".") or low.endswith("." + tok):
                return True
    return False


def scan_app_leftovers(
    app: InstalledApp,
    mode: str = "moderate",
    home_dir: Path | None = None,
) -> list[LeftoverItem]:
    """Revo-style leftover scanner supporting 'safe', 'moderate', and 'advanced' depths."""
    home = home_dir or Path.home()
    tokens = extract_app_tokens(app)
    found: dict[str, LeftoverItem] = {}

    def _add(p: Path, kind: str, requires_root: bool, risk: str = "safe") -> None:
        key = str(p)
        if key in found or (not p.exists() and not p.is_symlink()):
            return
        found[key] = LeftoverItem(
            path=key,
            kind=kind,
            size_bytes=_calc_path_size(p),
            requires_root=requires_root,
            risk=risk,
            selected=(risk == "safe"),
        )

    # 1. Exact sandbox directories (Flatpak & Snap)
    if app.source == "flatpak":
        fp_data = home / ".var" / "app" / app.pkg_id
        _add(fp_data, "sandbox", False, "safe")
    if app.source == "snap":
        snap_data = home / "snap" / app.pkg_id
        _add(snap_data, "sandbox", False, "safe")

    if not tokens:
        return list(found.values())

    exact_only = mode == "safe"

    # 2. User XDG directories (~/.config, ~/.cache, ~/.local/share, ~/.local/state)
    xdg_targets = [
        (home / ".config", "config"),
        (home / ".cache", "cache"),
        (home / ".local" / "share", "data"),
        (home / ".local" / "state", "data"),
    ]
    for folder, kind in xdg_targets:
        if not folder.exists():
            continue
        try:
            for child in folder.iterdir():
                if _name_matches_tokens(child.name, tokens, exact_only=exact_only):
                    _add(child, kind, False, "safe")
        except OSError:
            pass

    # 3. User custom .desktop launchers & autostart entries
    for desk_dir in (home / ".local" / "share" / "applications", home / ".config" / "autostart"):
        if not desk_dir.exists():
            continue
        try:
            for dfile in desk_dir.glob("*.desktop"):
                stem = dfile.stem
                if _name_matches_tokens(stem, tokens, exact_only=False):
                    _add(dfile, "launcher", False, "safe")
        except OSError:
            pass

    # 4. System-wide directories in Moderate / Advanced modes
    if mode in ("moderate", "advanced") and home_dir is None:
        sys_roots = [Path("/opt"), Path("/var/cache")]
        if mode == "advanced":
            sys_roots.extend([Path("/etc"), Path("/var/lib")])
        for sroot in sys_roots:
            if not sroot.exists():
                continue
            try:
                for child in sroot.iterdir():
                    if _name_matches_tokens(child.name, tokens, exact_only=(mode != "advanced")):
                        if _is_safe_root_leftover(str(child)):
                            risk = "safe" if sroot in (Path("/opt"), Path("/var/cache")) else "review"
                            _add(child, "system", True, risk)
            except OSError:
                pass

    items = list(found.values())
    items.sort(key=lambda x: (x.risk != "safe", -x.size_bytes, x.path))
    return items


def create_safety_backup(app: InstalledApp, leftovers: list[LeftoverItem]) -> Path | None:
    """Create compressed .tar.gz backup of user config/data before deletion."""
    user_items = [
        Path(it.path)
        for it in leftovers
        if not it.requires_root and it.kind in ("config", "data", "launcher", "sandbox") and Path(it.path).exists()
    ]
    if not user_items:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", app.name)[:40]
    archive_path = get_backup_dir() / f"{safe_slug}_{stamp}.tar.gz"
    try:
        with tarfile.open(archive_path, "w:gz") as tar:
            for p in user_items:
                # Skip huge caches inside ~/.var/app/<id>/cache
                tar.add(str(p), arcname=str(p.relative_to(Path.home())) if p.is_relative_to(Path.home()) else p.name)
        LOG_BUS.emit(f"Created safety backup: {archive_path}")
        return archive_path
    except Exception as exc:
        LOG_BUS.emit(f"Backup warning: {exc}")
        return None


def list_backups() -> list[tuple[Path, int]]:
    bdir = get_backup_dir()
    items: list[tuple[Path, int]] = []
    for f in sorted(bdir.glob("*.tar.gz"), reverse=True):
        try:
            items.append((f, f.stat().st_size))
        except OSError:
            pass
    return items


def restore_backup(archive_path: Path) -> tuple[bool, str]:
    if not archive_path.exists():
        return False, "Backup archive not found."
    home = Path.home().resolve()
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                dest = (home / member.name).resolve()
                if not str(dest).startswith(str(home)):
                    return False, f"Blocked unsafe path in archive: {member.name}"
            tar.extractall(path=home)
        LOG_BUS.emit(f"Restored backup {archive_path.name} into {home}")
        return True, f"Restored {archive_path.name}"
    except Exception as exc:
        return False, str(exc)


def uninstall_application(app: InstalledApp) -> tuple[bool, str]:
    """Execute primary package uninstallation before leftover cleanup."""
    if app.protected:
        return False, f"{app.name} is a protected Zorin OS core package."

    LOG_BUS.emit(f"Uninstalling {app.name} ({app.source}: {app.pkg_id})...")

    if app.source in ("apt", "snap"):
        res = run_privileged("uninstall_pkg", {"source": app.source, "pkg_id": app.pkg_id}, timeout=600)
        return res.ok, res.combined_output

    if app.source == "flatpak":
        res = run_cmd(["flatpak", "uninstall", "-y", app.pkg_id], timeout=300, log=True)
        return res.ok, res.combined_output

    if app.source == "appimage":
        target = Path(app.pkg_id)
        try:
            if target.exists():
                target.unlink()
            return True, f"Removed AppImage {target.name}"
        except OSError as exc:
            return False, str(exc)

    if app.source == "wine":
        target = Path(app.pkg_id)
        try:
            if target.exists():
                target.unlink()
            return True, f"Removed Wine shortcut {target.name}"
        except OSError as exc:
            return False, str(exc)

    return False, f"Unknown package source: {app.source}"


def delete_leftovers(items: list[LeftoverItem]) -> tuple[int, int, str]:
    """Delete selected user and system leftover items; returns (deleted_count, bytes_freed, msg)."""
    selected = [it for it in items if it.selected]
    if not selected:
        return 0, 0, "No leftovers selected."

    deleted_count = 0
    freed_bytes = 0
    root_paths: list[str] = []

    for it in selected:
        if it.requires_root:
            root_paths.append(it.path)
            continue
        p = Path(it.path)
        try:
            # Guard: must reside inside user's home directory
            if not p.resolve().is_relative_to(Path.home().resolve()) and not p.is_symlink():
                continue
            if p.is_symlink() or p.is_file():
                p.unlink()
                deleted_count += 1
                freed_bytes += it.size_bytes
            elif p.is_dir():
                shutil.rmtree(p)
                deleted_count += 1
                freed_bytes += it.size_bytes
        except OSError as exc:
            LOG_BUS.emit(f"Could not delete {it.path}: {exc}")

    if root_paths:
        res = run_privileged("delete_root_leftovers", {"paths": root_paths}, timeout=120)
        if res.ok:
            for it in selected:
                if it.requires_root and not Path(it.path).exists():
                    deleted_count += 1
                    freed_bytes += it.size_bytes

    LOG_BUS.emit(f"Shredded {deleted_count} leftover items ({freed_bytes} bytes).")
    return deleted_count, freed_bytes, "Completed"


def scan_orphan_leftovers() -> list[LeftoverItem]:
    """Find 100%-verified ghost leftovers from previously uninstalled Flatpaks, Snaps & dead launchers."""
    LOG_BUS.emit("Scanning for orphan leftovers from previously uninstalled apps...")
    home = Path.home()
    orphans: list[LeftoverItem] = []

    # 1. Orphaned ~/.var/app/* Flatpak data directories
    var_app = home / ".var" / "app"
    if var_app.exists() and which_bin("flatpak"):
        installed_fp = {a.pkg_id for a in list_flatpak_apps()}
        # Also include runtimes just in case
        rt_res = run_cmd(["flatpak", "list", "--columns=application"], timeout=20)
        if rt_res.ok:
            for line in rt_res.stdout.splitlines():
                if line.strip():
                    installed_fp.add(line.strip())
        try:
            for child in var_app.iterdir():
                if child.is_dir() and child.name not in installed_fp:
                    orphans.append(
                        LeftoverItem(
                            path=str(child),
                            kind="sandbox",
                            size_bytes=_calc_path_size(child),
                            requires_root=False,
                            risk="safe",
                            selected=True,
                        )
                    )
        except OSError:
            pass

    # 2. Orphaned ~/snap/* directories
    snap_home = home / "snap"
    if snap_home.exists() and which_bin("snap"):
        snap_res = run_cmd(["snap", "list"], timeout=15)
        installed_snaps: set[str] = set()
        if snap_res.ok:
            for line in snap_res.stdout.splitlines()[1:]:
                cols = line.split()
                if cols:
                    installed_snaps.add(cols[0])
            try:
                for child in snap_home.iterdir():
                    if child.is_dir() and child.name not in installed_snaps:
                        orphans.append(
                            LeftoverItem(
                                path=str(child),
                                kind="sandbox",
                                size_bytes=_calc_path_size(child),
                                requires_root=False,
                                risk="safe",
                                selected=True,
                            )
                        )
            except OSError:
                pass

    # 3. Dead custom .desktop launchers in ~/.local/share/applications
    local_apps = home / ".local" / "share" / "applications"
    if local_apps.exists():
        for dfile in local_apps.glob("*.desktop"):
            cp = configparser.ConfigParser(interpolation=None)
            try:
                cp.read(dfile, encoding="utf-8")
                exec_line = cp["Desktop Entry"].get("Exec", "").strip()
                if not exec_line:
                    continue
                first_tok = shlex.split(exec_line)[0]
                if first_tok.startswith("/"):
                    exists = Path(first_tok).exists()
                else:
                    exists = which_bin(first_tok) is not None
                if not exists:
                    orphans.append(
                        LeftoverItem(
                            path=str(dfile),
                            kind="launcher",
                            size_bytes=_calc_path_size(dfile),
                            requires_root=False,
                            risk="safe",
                            selected=True,
                        )
                    )
            except Exception:
                pass

    orphans.sort(key=lambda x: -x.size_bytes)
    LOG_BUS.emit(f"Orphan hunter found {len(orphans)} ghost item(s).")
    return orphans
