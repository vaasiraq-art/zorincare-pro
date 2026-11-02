"""Page 4: Revo-Style Universal App Uninstaller & Deep Leftover Hunter."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from zorincare.core.uninstaller import (
    InstalledApp,
    LeftoverItem,
    create_safety_backup,
    delete_leftovers,
    list_all_installed_apps,
    list_backups,
    restore_backup,
    scan_app_leftovers,
    scan_orphan_leftovers,
    uninstall_application,
)
from zorincare.i18n import SETTINGS, format_bytes, t
from zorincare.ui.widgets import make_badge


class UninstallerPage(Gtk.Box):
    def __init__(
        self,
        parent_window: Gtk.Window,
        notify_toast: Callable[[str], None],
        set_status: Callable[[str], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._win = parent_window
        self._notify = notify_toast
        self._set_status = set_status
        self._all_apps: list[InstalledApp] = []
        self._source_filter = "all"
        self._busy = False

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        clamp = Adw.Clamp(maximum_size=960, tightening_threshold=720)
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_top=20,
            margin_bottom=24,
            margin_start=20,
            margin_end=20,
        )

        # Hero Banner
        banner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        banner.add_css_class("hero-banner")
        title = Gtk.Label(label=t("uninst_headline"), xalign=0.0, wrap=True)
        title.add_css_class("page-title")
        desc = Gtk.Label(label=t("uninst_desc"), xalign=0.0, wrap=True)
        desc.add_css_class("dim-caption")

        top_tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.orphan_btn = Gtk.Button(label=t("uninst_orphan_btn"))
        self.orphan_btn.set_tooltip_text(t("uninst_orphan_tip"))
        self.orphan_btn.add_css_class("care-cta-button")
        self.orphan_btn.connect("clicked", self._on_hunt_orphans)

        self.backups_btn = Gtk.Button(label=t("uninst_backups_btn", count=len(list_backups())))
        self.backups_btn.connect("clicked", self._on_open_backups_dialog)

        refresh_btn = Gtk.Button(label=t("refresh"))
        refresh_btn.connect("clicked", lambda *_: self._load_apps())

        self.spinner = Gtk.Spinner()
        top_tools.append(self.orphan_btn)
        top_tools.append(self.backups_btn)
        top_tools.append(refresh_btn)
        top_tools.append(self.spinner)

        banner.append(title)
        banner.append(desc)
        banner.append(top_tools)
        content.append(banner)

        # Search + Source Filter + Scan Depth + Backup Toggle
        controls_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        controls_card.add_css_class("metric-card")

        filter_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.search_entry = Gtk.SearchEntry(placeholder_text=t("uninst_search_ph"), hexpand=True)
        self.search_entry.connect("search-changed", lambda *_: self._apply_filters())

        self.src_combo = Gtk.DropDown.new_from_strings(
            [t("uninst_filter_all"), "APT (.deb)", "Flatpak", "Snap", "AppImage", "Wine"]
        )
        self.src_combo.connect("notify::selected", self._on_source_changed)
        filter_row.append(self.search_entry)
        filter_row.append(self.src_combo)

        opts_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        depth_lbl = Gtk.Label(label=f"{t('uninst_scan_mode')}:")
        self.depth_combo = Gtk.DropDown.new_from_strings(
            [t("uninst_mode_safe"), t("uninst_mode_moderate"), t("uninst_mode_advanced")]
        )
        mode_idx = {"safe": 0, "moderate": 1, "advanced": 2}.get(
            SETTINGS.get("revo_scan_mode", "moderate"), 1
        )
        self.depth_combo.set_selected(mode_idx)
        self.depth_combo.connect("notify::selected", self._on_depth_changed)

        self.backup_chk = Gtk.CheckButton(
            label=t("uninst_backup_toggle"),
            active=bool(SETTINGS.get("backup_before_uninstall", True)),
        )
        self.backup_chk.connect(
            "toggled",
            lambda b: SETTINGS.set("backup_before_uninstall", b.get_active()),
        )

        opts_row.append(depth_lbl)
        opts_row.append(self.depth_combo)
        opts_row.append(self.backup_chk)

        controls_card.append(filter_row)
        controls_card.append(opts_row)
        content.append(controls_card)

        # Installed Apps List
        self.apps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.append(self.apps_box)

        clamp.set_child(content)
        scroller.set_child(clamp)
        self.append(scroller)

        GLib.idle_add(self._load_apps)

    def _current_scan_mode(self) -> str:
        idx = self.depth_combo.get_selected()
        return ["safe", "moderate", "advanced"][min(2, max(0, idx))]

    def _on_depth_changed(self, combo: Gtk.DropDown, _pspec) -> None:
        SETTINGS.set("revo_scan_mode", self._current_scan_mode())

    def _on_source_changed(self, combo: Gtk.DropDown, _pspec) -> None:
        idx = combo.get_selected()
        mapping = ["all", "apt", "flatpak", "snap", "appimage", "wine"]
        self._source_filter = mapping[idx] if idx < len(mapping) else "all"
        self._apply_filters()

    def _load_apps(self) -> bool:
        if self._busy:
            return False
        self._busy = True
        self.spinner.start()
        self._set_status(t("status_working"))

        def worker() -> None:
            apps = list_all_installed_apps()
            GLib.idle_add(self._on_apps_loaded, apps)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _on_apps_loaded(self, apps: list[InstalledApp]) -> bool:
        self._busy = False
        self.spinner.stop()
        self._set_status(t("status_ready"))
        self._all_apps = apps
        self.backups_btn.set_label(t("uninst_backups_btn", count=len(list_backups())))
        self._apply_filters()
        return False

    def _apply_filters(self) -> None:
        while (child := self.apps_box.get_first_child()) is not None:
            self.apps_box.remove(child)

        query = self.search_entry.get_text().strip().lower()
        filtered = [
            a
            for a in self._all_apps
            if (self._source_filter == "all" or a.source == self._source_filter)
            and (not query or query in a.name.lower() or query in a.pkg_id.lower())
        ]

        grp = Adw.PreferencesGroup(title=f"{len(filtered)} Applications")
        if not filtered:
            grp.add(Adw.ActionRow(title="No matching applications found."))
            self.apps_box.append(grp)
            return

        badge_style_map = {
            "apt": "badge-blue",
            "flatpak": "badge-cyan",
            "snap": "badge-amber",
            "appimage": "badge-blue",
            "wine": "badge-red",
        }

        for app in filtered[:180]:
            sub = f"{app.pkg_id}  •  v{app.version}"
            if app.size_bytes > 0:
                sub += f"  •  {format_bytes(app.size_bytes)}"
            row = Adw.ActionRow(title=app.name, subtitle=sub)
            row.add_prefix(Gtk.Image.new_from_icon_name("application-x-executable-symbolic"))
            row.add_suffix(make_badge(app.source.upper(), badge_style_map.get(app.source, "badge-blue")))

            scan_btn = Gtk.Button(label=t("uninst_btn_leftovers_only"), valign=Gtk.Align.CENTER)
            scan_btn.connect("clicked", self._on_scan_only, app)
            row.add_suffix(scan_btn)

            if app.protected:
                row.add_suffix(make_badge(t("uninst_protected"), "badge-amber"))
            else:
                rm_btn = Gtk.Button(label=t("uninst_btn_remove"), valign=Gtk.Align.CENTER)
                rm_btn.add_css_class("danger-pill-btn")
                rm_btn.connect("clicked", self._on_confirm_uninstall, app)
                row.add_suffix(rm_btn)

            grp.add(row)

        self.apps_box.append(grp)

    def _on_confirm_uninstall(self, _btn: Gtk.Button, app: InstalledApp) -> None:
        dlg = Adw.MessageDialog(
            transient_for=self._win,
            heading=t("uninst_confirm_title", name=app.name),
            body=t("uninst_confirm_body", name=app.name, source=app.source.upper()),
        )
        dlg.add_response("cancel", t("cancel"))
        dlg.add_response("remove", t("uninst_btn_remove"))
        dlg.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", self._on_confirm_response, app)
        dlg.present()

    def _on_confirm_response(self, dlg: Adw.MessageDialog, response: str, app: InstalledApp) -> None:
        dlg.close()
        if response != "remove":
            return

        mode = self._current_scan_mode()
        do_backup = self.backup_chk.get_active()
        self.spinner.start()
        self._set_status(t("status_working"))

        def worker() -> None:
            pre_leftovers = scan_app_leftovers(app, mode=mode)
            if do_backup and pre_leftovers:
                create_safety_backup(app, pre_leftovers)
            ok, msg = uninstall_application(app)
            post_leftovers = scan_app_leftovers(app, mode=mode)
            GLib.idle_add(self._after_pkg_uninstall, ok, msg, app, post_leftovers)

        threading.Thread(target=worker, daemon=True).start()

    def _after_pkg_uninstall(
        self,
        ok: bool,
        msg: str,
        app: InstalledApp,
        leftovers: list[LeftoverItem],
    ) -> bool:
        self.spinner.stop()
        self._set_status(t("status_ready"))
        self.backups_btn.set_label(t("uninst_backups_btn", count=len(list_backups())))
        if not ok:
            self._notify(msg or f"Could not uninstall {app.name}")
            return False

        self._load_apps()
        if leftovers:
            self._show_leftovers_dialog(f"{app.name} — {t('uninst_btn_leftovers_only')}", leftovers)
        else:
            self._notify(f"{app.name}: {t('uninst_no_leftovers')}")
        return False

    def _on_scan_only(self, _btn: Gtk.Button, app: InstalledApp) -> None:
        mode = self._current_scan_mode()
        self.spinner.start()

        def worker() -> None:
            items = scan_app_leftovers(app, mode=mode)
            GLib.idle_add(self._after_scan_only, app.name, items)

        threading.Thread(target=worker, daemon=True).start()

    def _on_hunt_orphans(self, _btn: Gtk.Button) -> None:
        self.spinner.start()

        def worker() -> None:
            items = scan_orphan_leftovers()
            GLib.idle_add(self._after_scan_only, t("uninst_orphan_btn"), items)

        threading.Thread(target=worker, daemon=True).start()

    def _after_scan_only(self, label: str, items: list[LeftoverItem]) -> bool:
        self.spinner.stop()
        if not items:
            self._notify(t("uninst_no_leftovers"))
        else:
            self._show_leftovers_dialog(label, items)
        return False

    def _show_leftovers_dialog(self, heading_prefix: str, items: list[LeftoverItem]) -> None:
        total_sz = sum(i.size_bytes for i in items)
        win = Gtk.Window(
            title=f"{heading_prefix} — {t('uninst_leftover_title', count=len(items), size=format_bytes(total_sz))}",
            transient_for=self._win,
            modal=True,
            default_width=760,
            default_height=500,
        )
        tv = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        tv.add_top_bar(hb)

        vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=14,
            margin_bottom=14,
            margin_start=16,
            margin_end=16,
        )

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        grp = Adw.PreferencesGroup(
            title=t("uninst_leftover_title", count=len(items), size=format_bytes(total_sz))
        )

        checks: list[tuple[LeftoverItem, Gtk.CheckButton]] = []
        for it in items:
            row = Adw.ActionRow(
                title=it.path,
                subtitle=f"{it.kind.upper()}  •  {format_bytes(it.size_bytes)}",
            )
            chk = Gtk.CheckButton(active=it.selected, valign=Gtk.Align.CENTER)
            checks.append((it, chk))
            row.add_prefix(chk)
            row.add_suffix(
                make_badge(
                    it.risk.upper(),
                    "badge-cyan" if it.risk == "safe" else "badge-amber",
                )
            )
            if it.requires_root:
                row.add_suffix(make_badge("Root", "badge-red"))
            grp.add(row)

        scroller.set_child(grp)
        vbox.append(scroller)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, halign=Gtk.Align.END)
        cancel_btn = Gtk.Button(label=t("close"))
        cancel_btn.connect("clicked", lambda *_: win.close())

        shred_btn = Gtk.Button(label=t("uninst_delete_selected"))
        shred_btn.add_css_class("danger-pill-btn")

        def on_shred(_b: Gtk.Button) -> None:
            for item_obj, chk_widget in checks:
                item_obj.selected = chk_widget.get_active()
            shred_btn.set_sensitive(False)

            def worker() -> None:
                cnt, freed, _ = delete_leftovers(items)
                GLib.idle_add(after_shred, cnt, freed)

            def after_shred(cnt: int, freed: int) -> bool:
                win.close()
                self._notify(t("uninst_removed_done", count=cnt, size=format_bytes(freed)))
                return False

            threading.Thread(target=worker, daemon=True).start()

        shred_btn.connect("clicked", on_shred)
        footer.append(cancel_btn)
        footer.append(shred_btn)
        vbox.append(footer)

        tv.set_content(vbox)
        win.set_content(tv)
        win.present()

    def _on_open_backups_dialog(self, _btn: Gtk.Button) -> None:
        backups = list_backups()
        win = Gtk.Window(
            title=t("uninst_backups_btn", count=len(backups)),
            transient_for=self._win,
            modal=True,
            default_width=640,
            default_height=420,
        )
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        grp = Adw.PreferencesGroup(
            margin_top=14,
            margin_bottom=14,
            margin_start=16,
            margin_end=16,
        )
        if not backups:
            grp.add(Adw.ActionRow(title="No safety backups created yet."))
        else:
            for bpath, bsize in backups:
                row = Adw.ActionRow(title=bpath.name, subtitle=format_bytes(bsize))
                rbtn = Gtk.Button(label="Restore", valign=Gtk.Align.CENTER)
                rbtn.connect("clicked", self._restore_single_backup, bpath, win)
                row.add_suffix(rbtn)
                grp.add(row)

        scroller.set_child(grp)
        tv.set_content(scroller)
        win.set_content(tv)
        win.present()

    def _restore_single_backup(self, _btn: Gtk.Button, path: Path, dlg_win: Gtk.Window) -> None:
        ok, msg = restore_backup(path)
        dlg_win.close()
        self._notify(msg)
