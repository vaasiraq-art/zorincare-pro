"""Page 1: AI Smart SystemCare (IObit Advanced SystemCare 1-Click Scan & Clean)."""

from __future__ import annotations

import threading
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from zorincare.core.system_care import (
    CareCategoryResult,
    CareScanReport,
    clean_selected_categories,
    run_full_care_scan,
)
from zorincare.i18n import format_bytes, t
from zorincare.ui.widgets import HealthScoreRing, make_badge


class CarePage(Gtk.Box):
    def __init__(self, notify_toast: Callable[[str], None], set_status: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._notify = notify_toast
        self._set_status = set_status
        self._report: CareScanReport | None = None
        self._check_map: dict[str, Gtk.CheckButton] = {}
        self._busy = False

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        clamp = Adw.Clamp(maximum_size=940, tightening_threshold=700)
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=20,
            margin_bottom=24,
            margin_start=20,
            margin_end=20,
        )

        # Hero Banner with Radial Health Ring + CTA
        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        hero.add_css_class("hero-banner")

        self.ring = HealthScoreRing(size=196)
        hero.append(self.ring)

        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, valign=Gtk.Align.CENTER, hexpand=True)
        title = Gtk.Label(label=t("care_headline"), xalign=0.0, wrap=True)
        title.add_css_class("page-title")
        desc = Gtk.Label(label=t("care_desc"), xalign=0.0, wrap=True)
        desc.add_css_class("dim-caption")

        self.summary_lbl = Gtk.Label(label=t("care_all_clean"), xalign=0.0, wrap=True)
        self.reclaim_lbl = Gtk.Label(label=t("care_reclaimable", size="0 B"), xalign=0.0)
        self.reclaim_lbl.add_css_class("metric-big")

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, margin_top=6)
        self.scan_btn = Gtk.Button(label=t("care_scan_now"))
        self.scan_btn.add_css_class("care-cta-button")
        self.scan_btn.connect("clicked", self._on_scan_clicked)

        self.fix_btn = Gtk.Button(label=t("care_fix_now"))
        self.fix_btn.add_css_class("fix-cta-button")
        self.fix_btn.set_sensitive(False)
        self.fix_btn.connect("clicked", self._on_fix_clicked)

        btn_row.append(self.scan_btn)
        btn_row.append(self.fix_btn)

        right_col.append(title)
        right_col.append(desc)
        right_col.append(self.reclaim_lbl)
        right_col.append(self.summary_lbl)
        right_col.append(btn_row)
        hero.append(right_col)
        content.append(hero)

        # Selection toolbar
        sel_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_all = Gtk.Button(label=t("care_select_all"))
        btn_all.connect("clicked", lambda *_: self._toggle_all(True))
        btn_none = Gtk.Button(label=t("care_deselect_all"))
        btn_none.connect("clicked", lambda *_: self._toggle_all(False))
        sel_bar.append(btn_all)
        sel_bar.append(btn_none)
        content.append(sel_bar)

        # Categories container
        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.append(self.results_box)

        clamp.set_child(content)
        scroller.set_child(clamp)
        self.append(scroller)

        # Trigger initial scan automatically on launch
        GLib.idle_add(self._start_scan)

    def _toggle_all(self, state: bool) -> None:
        for chk in self._check_map.values():
            chk.set_active(state)

    def _on_scan_clicked(self, _btn: Gtk.Button) -> None:
        self._start_scan()

    def _start_scan(self) -> bool:
        if self._busy:
            return False
        self._busy = True
        self.ring.set_scanning(True)
        self.scan_btn.set_sensitive(False)
        self.scan_btn.set_label(t("care_scanning"))
        self.fix_btn.set_sensitive(False)
        self._set_status(t("care_scanning"))

        def worker() -> None:
            rep = run_full_care_scan()
            GLib.idle_add(self._on_scan_done, rep)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _on_scan_done(self, rep: CareScanReport) -> bool:
        self._busy = False
        self._report = rep
        self.ring.set_scanning(False)
        self.ring.set_score(rep.health_score)
        self.scan_btn.set_sensitive(True)
        self.scan_btn.set_label(t("care_scan_now"))

        self.reclaim_lbl.set_label(t("care_reclaimable", size=format_bytes(rep.total_bytes)))
        if rep.total_issues > 0:
            self.summary_lbl.set_label(t("care_items_found", count=rep.total_issues))
            self.fix_btn.set_sensitive(True)
        else:
            self.summary_lbl.set_label(t("care_all_clean"))
            self.fix_btn.set_sensitive(False)

        self._rebuild_category_rows(rep.categories)
        self._set_status(t("status_ready"))
        return False

    def _rebuild_category_rows(self, categories: list[CareCategoryResult]) -> None:
        while (child := self.results_box.get_first_child()) is not None:
            self.results_box.remove(child)
        self._check_map.clear()

        group = Adw.PreferencesGroup()
        for cat in categories:
            if cat.sample_items:
                row = Adw.ExpanderRow(
                    title=t(cat.title_key),
                    subtitle=t(cat.desc_key),
                )
                for sample in cat.sample_items[:6]:
                    srow = Adw.ActionRow(title=sample)
                    row.add_row(srow)
            else:
                row = Adw.ActionRow(
                    title=t(cat.title_key),
                    subtitle=t(cat.desc_key),
                )

            chk = Gtk.CheckButton(active=cat.selected)
            chk.set_valign(Gtk.Align.CENTER)
            self._check_map[cat.category_id] = chk
            row.add_prefix(chk)

            icon = Gtk.Image.new_from_icon_name(cat.icon_name)
            row.add_prefix(icon)

            if cat.requires_root:
                row.add_suffix(make_badge("Root", "badge-amber"))

            if cat.items_count > 0:
                sz_txt = format_bytes(cat.size_bytes) if cat.size_bytes > 0 else f"{cat.items_count}"
                row.add_suffix(make_badge(sz_txt, "badge-cyan"))
            else:
                row.add_suffix(make_badge("Clean", "badge-blue"))

            group.add(row)

        self.results_box.append(group)

    def _on_fix_clicked(self, _btn: Gtk.Button) -> None:
        if self._busy or not self._report:
            return
        selected_ids = [cid for cid, chk in self._check_map.items() if chk.get_active()]
        if not selected_ids:
            return

        reclaim_est = sum(
            c.size_bytes for c in self._report.categories if c.category_id in selected_ids and c.items_count > 0
        )
        self._busy = True
        self.ring.set_scanning(True)
        self.fix_btn.set_sensitive(False)
        self.fix_btn.set_label(t("care_fixing"))
        self.scan_btn.set_sensitive(False)
        self._set_status(t("care_fixing"))

        def worker() -> None:
            ok, msg = clean_selected_categories(selected_ids)
            new_rep = run_full_care_scan()
            GLib.idle_add(self._on_fix_done, ok, msg, reclaim_est, len(selected_ids), new_rep)

        threading.Thread(target=worker, daemon=True).start()

    def _on_fix_done(
        self,
        ok: bool,
        msg: str,
        reclaim_est: int,
        count: int,
        new_rep: CareScanReport,
    ) -> bool:
        self.fix_btn.set_label(t("care_fix_now"))
        self._on_scan_done(new_rep)
        if ok:
            self._notify(t("care_cleaned_toast", size=format_bytes(reclaim_est), count=count))
        else:
            self._notify(msg)
        return False
