#!/usr/bin/env python3
"""Cross-platform pure-Python Debian (.deb) package builder for ZorinCare Pro.

Generates a spec-compliant Debian 2.0 `ar` binary package with Unix permissions
and LF line endings on both Linux and Windows hosts.
"""

from __future__ import annotations

from pathlib import Path
import gzip
import hashlib
import io
import tarfile
import time

PACKAGE_NAME = "zorincare-pro"
PACKAGE_VERSION = "1.0.0"
ARCH = "all"


def _normalize_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _add_tar_dir(tar: tarfile.TarFile, arc_dir: str, mtime: int) -> None:
    ti = tarfile.TarInfo(name=arc_dir.rstrip("/") + "/")
    ti.type = tarfile.DIRTYPE
    ti.mode = 0o755
    ti.uid = 0
    ti.gid = 0
    ti.uname = "root"
    ti.gname = "root"
    ti.mtime = mtime
    tar.addfile(ti)


def _add_tar_bytes(
    tar: tarfile.TarFile,
    arc_path: str,
    payload: bytes,
    mode: int,
    mtime: int,
) -> None:
    ti = tarfile.TarInfo(name=arc_path)
    ti.type = tarfile.REGTYPE
    ti.size = len(payload)
    ti.mode = mode
    ti.uid = 0
    ti.gid = 0
    ti.uname = "root"
    ti.gname = "root"
    ti.mtime = mtime
    tar.addfile(ti, io.BytesIO(payload))


def _make_tar_gz(builder_fn) -> bytes:
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w", format=tarfile.GNU_FORMAT) as tar:
        builder_fn(tar)
    gz_out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz_out, mtime=0) as gz:
        gz.write(raw_tar.getvalue())
    return gz_out.getvalue()


def _ar_member(name: str, data: bytes, mtime: int) -> bytes:
    header = (
        f"{name:<16}"
        f"{mtime:<12}"
        f"{0:<6}"
        f"{0:<6}"
        f"{'100644':<8}"
        f"{len(data):<10}"
        "`\n"
    ).encode("ascii")
    assert len(header) == 60, f"Invalid ar header length: {len(header)}"
    pad = b"\n" if (len(data) % 2 == 1) else b""
    return header + data + pad


def build_deb(project_root: Path, output_dir: Path | None = None) -> Path:
    mtime = int(time.time())
    out_dir = output_dir or (project_root / "dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    deb_path = out_dir / f"{PACKAGE_NAME}_{PACKAGE_VERSION}_{ARCH}.deb"

    # Collect payload files: (arc_rel_path_without_leading_slash, bytes, unix_mode)
    staged_files: list[tuple[str, bytes, int]] = []

    # 1. /usr/bin/zorincare-pro executable wrapper
    bin_launcher = _normalize_lf(
        b"#!/usr/bin/env bash\n"
        b"export PYTHONPATH=\"/usr/share/zorincare-pro:${PYTHONPATH:-}\"\n"
        b"exec /usr/bin/python3 -m zorincare.main \"$@\"\n"
    )
    staged_files.append(("usr/bin/zorincare-pro", bin_launcher, 0o755))

    # 2. /usr/lib/zorincare-pro/zorincare-root-helper (Polkit target)
    helper_src = project_root / "zorincare" / "core" / "root_helper.py"
    staged_files.append(
        (
            "usr/lib/zorincare-pro/zorincare-root-helper",
            _normalize_lf(helper_src.read_bytes()),
            0o755,
        )
    )

    # 3. Python package tree -> /usr/share/zorincare-pro/zorincare/...
    pkg_dir = project_root / "zorincare"
    for py_file in sorted(pkg_dir.rglob("*.py")):
        rel = py_file.relative_to(project_root).as_posix()
        staged_files.append(
            (f"usr/share/zorincare-pro/{rel}", _normalize_lf(py_file.read_bytes()), 0o644)
        )

    # 4. Desktop file, Polkit policy, SVG icon
    staged_files.append(
        (
            "usr/share/applications/com.zorincare.pro.desktop",
            _normalize_lf((project_root / "data" / "com.zorincare.pro.desktop").read_bytes()),
            0o644,
        )
    )
    staged_files.append(
        (
            "usr/share/polkit-1/actions/com.zorincare.pro.policy",
            _normalize_lf((project_root / "data" / "com.zorincare.pro.policy").read_bytes()),
            0o644,
        )
    )
    staged_files.append(
        (
            "usr/share/icons/hicolor/scalable/apps/com.zorincare.pro.svg",
            _normalize_lf((project_root / "data" / "icons" / "com.zorincare.pro.svg").read_bytes()),
            0o644,
        )
    )

    total_bytes = sum(len(b) for _, b, _ in staged_files)
    installed_kb = max(64, (total_bytes + 1023) // 1024)

    # Build data.tar.gz with explicit parent directory entries
    def populate_data(tar: tarfile.TarFile) -> None:
        created_dirs: set[str] = set()
        _add_tar_dir(tar, ".", mtime)
        created_dirs.add(".")

        for rel_path, content, mode in staged_files:
            parts = rel_path.split("/")
            for depth in range(1, len(parts)):
                d_arc = "./" + "/".join(parts[:depth])
                if d_arc not in created_dirs:
                    _add_tar_dir(tar, d_arc, mtime)
                    created_dirs.add(d_arc)
            _add_tar_bytes(tar, "./" + rel_path, content, mode, mtime)

    data_tar_gz = _make_tar_gz(populate_data)

    # Build control.tar.gz
    md5_lines = [
        f"{hashlib.md5(content).hexdigest()}  {rel_path}"
        for rel_path, content, _ in staged_files
    ]
    md5sums_bytes = ("\n".join(md5_lines) + "\n").encode("utf-8")

    control_text = (
        f"Package: {PACKAGE_NAME}\n"
        f"Version: {PACKAGE_VERSION}\n"
        "Section: admin\n"
        "Priority: optional\n"
        f"Architecture: {ARCH}\n"
        f"Installed-Size: {installed_kb}\n"
        "Maintainer: ZorinCare Pro Contributors <noreply@github.com>\n"
        "Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0, gir1.2-adw-1, pkexec | policykit-1\n"
        "Recommends: ubuntu-drivers-common, fwupd, ufw, pciutils, usbutils, power-profiles-daemon\n"
        "Homepage: https://github.com/vaasiraq-art/zorincare-pro\n"
        "Description: System Optimizer, Driver Booster & Deep Uninstaller for Zorin OS 18.1 Pro\n"
        " All-in-one native GTK4 + Libadwaita system care utility built for Zorin OS 18.1\n"
        " Pro and Ubuntu 24.04 LTS. Features 1-click Smart SystemCare junk cleaning,\n"
        " RAM & Kernel 6.17 Turbo Boost, GPU/Wi-Fi Driver & LVFS Firmware Booster,\n"
        " Revo-style Deep Uninstaller with leftover hunter, and a full PC Control Center\n"
        " in switchable English and Arabic (RTL).\n"
    ).encode("utf-8")

    postinst_bytes = _normalize_lf(
        b"#!/bin/sh\n"
        b"set -e\n"
        b"if command -v update-desktop-database >/dev/null 2>&1; then\n"
        b"    update-desktop-database -q /usr/share/applications || true\n"
        b"fi\n"
        b"if command -v gtk-update-icon-cache >/dev/null 2>&1; then\n"
        b"    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true\n"
        b"fi\n"
        b"exit 0\n"
    )

    def populate_control(tar: tarfile.TarFile) -> None:
        _add_tar_dir(tar, ".", mtime)
        _add_tar_bytes(tar, "./control", control_text, 0o644, mtime)
        _add_tar_bytes(tar, "./md5sums", md5sums_bytes, 0o644, mtime)
        _add_tar_bytes(tar, "./postinst", postinst_bytes, 0o755, mtime)

    control_tar_gz = _make_tar_gz(populate_control)

    # Assemble Debian 2.0 `ar` archive
    ar_bytes = (
        b"!<arch>\n"
        + _ar_member("debian-binary", b"2.0\n", mtime)
        + _ar_member("control.tar.gz", control_tar_gz, mtime)
        + _ar_member("data.tar.gz", data_tar_gz, mtime)
    )
    deb_path.write_bytes(ar_bytes)
    print(f"Built Debian package: {deb_path} ({len(ar_bytes):,} bytes)")
    return deb_path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    build_deb(root)
