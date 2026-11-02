"""Smart SystemCare engine (IObit Advanced SystemCare style) for Zorin OS 18.1 Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import shutil

from zorincare.core.runner import LOG_BUS, run_cmd, run_privileged, which_bin


SAFE_USER_CACHE_DIRS = (
    "pip",
    "npm",
    "yarn",
    "pnpm",
    "mesa_shader_cache",
    "mesa_shader_cache_db",
    "AMD",
    "nvidia",
    "go-build",
    "cargo",
    "fontconfig",
    "webkitgtk",
    "gstreamer-1.0",
)

ROOT_CATEGORIES = {
    "apt_cache",
    "apt_orphans",
    "dpkg_rc",
    "snap_disabled",
    "journal_logs",
    "rotated_logs",
    "crash_dumps",
}


@dataclass
class CareCategoryResult:
    category_id: str
    title_key: str
    desc_key: str
    icon_name: str
    requires_root: bool
    items_count: int = 0
    size_bytes: int = 0
    sample_items: list[str] = field(default_factory=list)
    selected: bool = True


@dataclass
class CareScanReport:
    health_score: int
    total_bytes: int
    total_issues: int
    categories: list[CareCategoryResult]


def _dir_size_and_count(path: Path, max_samples: int = 8) -> tuple[int, int, list[str]]:
    if not path.exists():
        return 0, 0, []
    total_size = 0
    count = 0
    samples: list[str] = []
    try:
        for root, _, files in os.walk(path, followlinks=False):
            for fname in files:
                fpath = Path(root) / fname
                try:
                    if not fpath.is_symlink():
                        total_size += fpath.stat().st_size
                    count += 1
                    if len(samples) < max_samples:
                        samples.append(str(fpath))
                except OSError:
                    pass
    except OSError:
        pass
    return total_size, count, samples


def _parse_human_size_to_bytes(text: str) -> int:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMGTPE]?i?B|B)", text, re.IGNORECASE)
    if not match:
        return 0
    val = float(match.group(1))
    unit = match.group(2).upper().replace("IB", "B")
    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
    }
    return int(val * multipliers.get(unit, 1))


def scan_apt_cache() -> CareCategoryResult:
    res = CareCategoryResult(
        "apt_cache",
        "cat_apt_cache",
        "cat_apt_cache_desc",
        "package-x-generic-symbolic",
        requires_root=True,
    )
    apt_dir = Path("/var/cache/apt/archives")
    if apt_dir.exists():
        try:
            for deb in apt_dir.glob("*.deb"):
                try:
                    res.size_bytes += deb.stat().st_size
                    res.items_count += 1
                    if len(res.sample_items) < 6:
                        res.sample_items.append(deb.name)
                except OSError:
                    pass
        except OSError:
            pass
    return res


def scan_apt_orphans() -> CareCategoryResult:
    res = CareCategoryResult(
        "apt_orphans",
        "cat_apt_orphans",
        "cat_apt_orphans_desc",
        "user-trash-symbolic",
        requires_root=True,
    )
    if which_bin("apt-get"):
        out = run_cmd(["apt-get", "-s", "autoremove"], timeout=30)
        if out.ok:
            for line in out.stdout.splitlines():
                if line.startswith("Remv "):
                    parts = line.split()
                    if len(parts) >= 2:
                        res.items_count += 1
                        if len(res.sample_items) < 8:
                            res.sample_items.append(parts[1])
                elif "disk space will be freed" in line:
                    res.size_bytes = _parse_human_size_to_bytes(line)
    return res


def scan_dpkg_residual() -> CareCategoryResult:
    res = CareCategoryResult(
        "dpkg_rc",
        "cat_dpkg_rc",
        "cat_dpkg_rc_desc",
        "document-properties-symbolic",
        requires_root=True,
    )
    if which_bin("dpkg"):
        out = run_cmd(["dpkg", "-l"], timeout=20)
        if out.ok:
            for line in out.stdout.splitlines():
                if line.startswith("rc "):
                    cols = line.split()
                    if len(cols) >= 2:
                        res.items_count += 1
                        res.size_bytes += 32 * 1024
                        if len(res.sample_items) < 8:
                            res.sample_items.append(cols[1])
    return res


def scan_flatpak_unused() -> CareCategoryResult:
    res = CareCategoryResult(
        "flatpak_unused",
        "cat_flatpak_unused",
        "cat_flatpak_unused_desc",
        "system-software-install-symbolic",
        requires_root=False,
    )
    if which_bin("flatpak"):
        out = run_cmd(["flatpak", "list", "--unused", "--columns=application,size"], timeout=25)
        if out.ok and out.stdout.strip():
            for line in out.stdout.strip().splitlines():
                parts = line.split("\t")
                app_id = parts[0].strip()
                if not app_id or app_id.lower() == "application id":
                    continue
                res.items_count += 1
                if len(parts) > 1:
                    res.size_bytes += _parse_human_size_to_bytes(parts[1])
                if len(res.sample_items) < 8:
                    res.sample_items.append(app_id)
    return res


def scan_snap_disabled() -> CareCategoryResult:
    res = CareCategoryResult(
        "snap_disabled",
        "cat_snap_disabled",
        "cat_snap_disabled_desc",
        "drive-harddisk-symbolic",
        requires_root=True,
    )
    if which_bin("snap"):
        out = run_cmd(["snap", "list", "--all"], timeout=20)
        if out.ok:
            for line in out.stdout.splitlines()[1:]:
                cols = line.split()
                if len(cols) >= 6 and "disabled" in cols[5]:
                    snap_name, rev = cols[0], cols[2]
                    res.items_count += 1
                    res.sample_items.append(f"{snap_name} (rev {rev})")
                    snap_file = Path(f"/var/lib/snapd/snaps/{snap_name}_{rev}.snap")
                    if snap_file.exists():
                        try:
                            res.size_bytes += snap_file.stat().st_size
                        except OSError:
                            pass
    return res


def scan_journal_logs() -> CareCategoryResult:
    res = CareCategoryResult(
        "journal_logs",
        "cat_journal_logs",
        "cat_journal_logs_desc",
        "text-x-generic-symbolic",
        requires_root=True,
    )
    if which_bin("journalctl"):
        out = run_cmd(["journalctl", "--disk-usage"], timeout=15)
        if out.ok:
            used = _parse_human_size_to_bytes(out.stdout)
            threshold = 50 * 1024 * 1024  # Keep 50 MB
            if used > threshold:
                res.size_bytes = used - threshold
                res.items_count = 1
                res.sample_items.append(out.stdout.strip())
    return res


def scan_rotated_logs() -> CareCategoryResult:
    res = CareCategoryResult(
        "rotated_logs",
        "cat_rotated_logs",
        "cat_rotated_logs_desc",
        "folder-documents-symbolic",
        requires_root=True,
    )
    var_log = Path("/var/log")
    if var_log.exists():
        try:
            for root, _, files in os.walk(var_log, followlinks=False):
                for fname in files:
                    if fname.endswith(".gz") or fname.endswith(".old") or re.search(r"\.\d+$", fname):
                        fpath = Path(root) / fname
                        try:
                            res.size_bytes += fpath.stat().st_size
                            res.items_count += 1
                            if len(res.sample_items) < 6:
                                res.sample_items.append(str(fpath))
                        except OSError:
                            pass
        except OSError:
            pass
    return res


def scan_thumbnails() -> CareCategoryResult:
    res = CareCategoryResult(
        "thumbnails",
        "cat_thumbnails",
        "cat_thumbnails_desc",
        "image-x-generic-symbolic",
        requires_root=False,
    )
    thumb_dir = Path.home() / ".cache" / "thumbnails"
    sz, cnt, samples = _dir_size_and_count(thumb_dir)
    res.size_bytes = sz
    res.items_count = cnt
    res.sample_items = samples
    return res


def scan_user_caches() -> CareCategoryResult:
    res = CareCategoryResult(
        "user_cache",
        "cat_user_cache",
        "cat_user_cache_desc",
        "folder-templates-symbolic",
        requires_root=False,
    )
    cache_root = Path.home() / ".cache"
    if cache_root.exists():
        for name in SAFE_USER_CACHE_DIRS:
            sub = cache_root / name
            if sub.exists():
                sz, cnt, _ = _dir_size_and_count(sub, max_samples=2)
                if cnt > 0:
                    res.size_bytes += sz
                    res.items_count += cnt
                    res.sample_items.append(f"~/.cache/{name}")
    return res


def scan_crash_dumps() -> CareCategoryResult:
    res = CareCategoryResult(
        "crash_dumps",
        "cat_crash_dumps",
        "cat_crash_dumps_desc",
        "dialog-warning-symbolic",
        requires_root=True,
    )
    for cdir in (Path("/var/crash"), Path("/var/lib/systemd/coredump")):
        if cdir.exists():
            try:
                for item in cdir.iterdir():
                    if item.is_file():
                        res.size_bytes += item.stat().st_size
                        res.items_count += 1
                        res.sample_items.append(str(item))
            except OSError:
                pass
    return res


def scan_trash() -> CareCategoryResult:
    res = CareCategoryResult(
        "trash",
        "cat_trash",
        "cat_trash_desc",
        "user-trash-full-symbolic",
        requires_root=False,
    )
    trash_files = Path.home() / ".local" / "share" / "Trash" / "files"
    sz, cnt, samples = _dir_size_and_count(trash_files)
    res.size_bytes = sz
    res.items_count = cnt
    res.sample_items = samples
    return res


def scan_broken_symlinks() -> CareCategoryResult:
    res = CareCategoryResult(
        "broken_links",
        "cat_broken_links",
        "cat_broken_links_desc",
        "emblem-symbolic-link",
        requires_root=False,
    )
    home = Path.home()
    targets = [
        home / ".local" / "bin",
        home / ".local" / "share" / "applications",
        home / "Desktop",
    ]
    for folder in targets:
        if folder.exists():
            try:
                for entry in folder.iterdir():
                    if entry.is_symlink() and not entry.exists():
                        res.items_count += 1
                        res.sample_items.append(str(entry))
            except OSError:
                pass
    return res


def compute_health_score(categories: list[CareCategoryResult]) -> int:
    total_mb = sum(c.size_bytes for c in categories) / (1024 * 1024)
    active_cats = sum(1 for c in categories if c.items_count > 0)

    penalty = 0.0
    if total_mb > 0:
        penalty += min(32.0, total_mb / 120.0 * 8.0)
    penalty += active_cats * 2.5

    for c in categories:
        if c.category_id == "crash_dumps" and c.items_count > 0:
            penalty += 6.0
        elif c.category_id == "apt_orphans" and c.items_count > 0:
            penalty += 4.0

    score = int(round(max(38.0, min(100.0, 100.0 - penalty))))
    return score


def run_full_care_scan() -> CareScanReport:
    LOG_BUS.emit("Starting Smart SystemCare 12-point deep scan...")
    scanners = [
        scan_apt_cache,
        scan_apt_orphans,
        scan_dpkg_residual,
        scan_flatpak_unused,
        scan_snap_disabled,
        scan_journal_logs,
        scan_rotated_logs,
        scan_thumbnails,
        scan_user_caches,
        scan_crash_dumps,
        scan_trash,
        scan_broken_symlinks,
    ]
    results = [fn() for fn in scanners]
    for r in results:
        r.selected = r.items_count > 0

    total_bytes = sum(r.size_bytes for r in results)
    total_issues = sum(1 for r in results if r.items_count > 0)
    score = compute_health_score(results)
    LOG_BUS.emit(
        f"Scan complete: Health Score={score}/100, {total_issues} categories with items."
    )
    return CareScanReport(
        health_score=score,
        total_bytes=total_bytes,
        total_issues=total_issues,
        categories=results,
    )


def _empty_dir_contents(folder: Path) -> None:
    if not folder.exists():
        return
    for child in folder.iterdir():
        try:
            if child.is_symlink() or child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
        except OSError:
            pass


def clean_selected_categories(selected_ids: list[str]) -> tuple[bool, str]:
    """Clean user-space categories directly and batch root categories in one pkexec call."""
    if not selected_ids:
        return True, "Nothing selected."

    LOG_BUS.emit(f"Cleaning categories: {', '.join(selected_ids)}")
    home = Path.home()

    # 1. User-space cleanups (no root required)
    if "thumbnails" in selected_ids:
        _empty_dir_contents(home / ".cache" / "thumbnails")

    if "user_cache" in selected_ids:
        cache_root = home / ".cache"
        for name in SAFE_USER_CACHE_DIRS:
            _empty_dir_contents(cache_root / name)

    if "trash" in selected_ids:
        _empty_dir_contents(home / ".local" / "share" / "Trash" / "files")
        _empty_dir_contents(home / ".local" / "share" / "Trash" / "info")

    if "broken_links" in selected_ids:
        for folder in (home / ".local" / "bin", home / ".local" / "share" / "applications", home / "Desktop"):
            if folder.exists():
                for entry in folder.iterdir():
                    try:
                        if entry.is_symlink() and not entry.exists():
                            entry.unlink()
                    except OSError:
                        pass

    if "flatpak_unused" in selected_ids and which_bin("flatpak"):
        run_cmd(["flatpak", "uninstall", "--unused", "-y"], timeout=180, log=True)

    # 2. Root-space cleanups batched into a single Polkit prompt
    root_needed = [cid for cid in selected_ids if cid in ROOT_CATEGORIES]
    if root_needed:
        res = run_privileged("system_care_clean", {"categories": root_needed}, timeout=600)
        if not res.ok:
            return False, res.combined_output or "Root cleanup cancelled or failed."

    return True, "System cleanup finished."
