#!/usr/bin/env python3
"""Entry point for ZorinCare Pro (GTK4 GUI + CLI diagnostic modes)."""

from __future__ import annotations

import argparse
import sys

from zorincare import APP_ID, APP_NAME, APP_VERSION
from zorincare.core.distro import detect_system_profile
from zorincare.core.system_care import run_full_care_scan
from zorincare.i18n import SETTINGS, format_bytes


def _run_cli_scan() -> int:
    prof = detect_system_profile()
    print(f"=== {APP_NAME} v{APP_VERSION} — CLI System Diagnostic ===")
    print(f"OS      : {prof.distro_name} ({prof.arch})")
    print(f"Kernel  : {prof.kernel}")
    print(f"CPU     : {prof.cpu_model} ({prof.cpu_cores} cores)")
    print(f"RAM     : {format_bytes(prof.total_ram_bytes)}")
    print("-" * 56)

    rep = run_full_care_scan()
    print(f"Health Score      : {rep.health_score} / 100")
    print(f"Reclaimable Space : {format_bytes(rep.total_bytes)}")
    print(f"Categories Found  : {rep.total_issues}")
    for cat in rep.categories:
        status = f"{cat.items_count} item(s), {format_bytes(cat.size_bytes)}" if cat.items_count else "Clean"
        print(f"  - {cat.category_id:<18} : {status}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="zorincare-pro",
        description=f"{APP_NAME} v{APP_VERSION} — System Optimizer, Driver Booster & Deep Uninstaller for Zorin OS 18.1 Pro",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument("--cli-scan", action="store_true", help="Run a non-interactive 12-point health scan in terminal")
    parser.add_argument("--lang", choices=["en", "ar"], help="Start interface in English (en) or Arabic (ar)")
    args, gtk_rest = parser.parse_known_args(argv)

    if args.lang:
        SETTINGS.lang = args.lang

    if args.cli_scan:
        return _run_cli_scan()

    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gio
    except ImportError as exc:
        print(
            "Error: GTK4 / Libadwaita Python bindings are required to launch the ZorinCare Pro GUI.\n"
            "On Zorin OS 18.1 Pro / Ubuntu 24.04, run:\n"
            "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        return 1

    from zorincare.ui.window import ZorinCareWindow

    class ZorinCareApp(Adw.Application):
        def __init__(self) -> None:
            super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

        def do_activate(self) -> None:
            win = self.props.active_window
            if not win:
                win = ZorinCareWindow(self)
            win.present()

    app = ZorinCareApp()
    return app.run([sys.argv[0]] + gtk_rest)


if __name__ == "__main__":
    raise SystemExit(main())
