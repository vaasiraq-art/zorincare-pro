"""Page 2: Turbo Boost & Zorin Kernel 6.17 Performance Optimizer."""

from __future__ import annotations

import threading
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from zorincare.core.turbo_boost import (
    apply_selected_kernel_tweaks,
    apply_turbo_mode,
    boost_ram_memory,
    get_active_power_profile,
    get_current_turbo_mode,
    get_kernel_tweak_states,
    read_memory_snapshot,
    reset_kernel_tweaks,
)
from zorincare.i18n import format_bytes, t
from zorincare.ui.widgets import MetricGaugeCard, make_badge


class BoosterPage(Gtk.Box):
    def __init__(self, notify_toast: Callable[[str], None], set_status: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._notify = notify_toast
        self._set_status = set_status
        self._sysctl_checks: dict[str, Gtk.CheckButton] = {}

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

        # Header Banner
        banner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        banner.add_css_class("hero-banner")
        h_lbl = Gtk.Label(label=t("boost_headline"), xalign=0.0, wrap=True)
        h_lbl.add_css_class("page-title")
        d_lbl = Gtk.Label(label=t("boost_desc"), xalign=0.0, wrap=True)
        d_lbl.add_css_class("dim-caption")
        banner.append(h_lbl)
        banner.append(d_lbl)
        content.append(banner)

        # Live RAM + Swap Cards & Instant RAM Booster
        mem_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14, homogeneous=True)
        self.ram_card = MetricGaugeCard(t("ctrl_ram"), "drive-multidisk-symbolic")
        self.swap_card = MetricGaugeCard(t("ctrl_swap"), "media-flash-symbolic")
        mem_row.append(self.ram_card)
        mem_row.append(self.swap_card)
        content.append(mem_row)

        ram_group = Adw.PreferencesGroup(title=t("boost_ram_title"), description=t("boost_ram_sub"))
        ram_action = Adw.ActionRow(title=t("boost_ram_title"), subtitle=t("boost_ram_sub"))
        self.ram_btn = Gtk.Button(label=t("boost_ram_btn"), valign=Gtk.Align.CENTER)
        self.ram_btn.add_css_class("care-cta-button")
        self.ram_btn.connect("clicked", self._on_boost_ram)
        ram_action.add_suffix(self.ram_btn)
        ram_group.add(ram_action)
        content.append(ram_group)

        # Turbo Boost Mode Profiles
        self.mode_group = Adw.PreferencesGroup(title=t("boost_mode_title"))
        modes = [
            ("normal", "boost_mode_normal", "weather-clear-symbolic"),
            ("work", "boost_mode_work", "applications-engineering-symbolic"),
            ("game", "boost_mode_game", "input-gaming-symbolic"),
            ("saver", "boost_mode_saver", "battery-good-symbolic"),
        ]
        self._mode_badges: dict[str, Gtk.Label] = {}
        active_mode = get_current_turbo_mode()
        for mid, mkey, micon in modes:
            mrow = Adw.ActionRow(title=t(mkey))
            mrow.add_prefix(Gtk.Image.new_from_icon_name(micon))
            badge = make_badge(
                t("active") if mid == active_mode else t("inactive"),
                "badge-cyan" if mid == active_mode else "badge-blue",
            )
            self._mode_badges[mid] = badge
            mrow.add_suffix(badge)

            btn = Gtk.Button(label=t("boost_activate"), valign=Gtk.Align.CENTER)
            btn.connect("clicked", self._on_mode_selected, mid)
            mrow.add_suffix(btn)
            self.mode_group.add(mrow)

        self.pwr_row = Adw.ActionRow(title=t("boost_power_title"), subtitle=get_active_power_profile())
        self.mode_group.add(self.pwr_row)
        content.append(self.mode_group)

        # Kernel 6.17 Sysctl Tweaks
        self.sysctl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.append(self.sysctl_box)

        sys_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        apply_btn = Gtk.Button(label=t("boost_apply_sysctl"))
        apply_btn.add_css_class("fix-cta-button")
        apply_btn.connect("clicked", self._on_apply_sysctl)
        reset_btn = Gtk.Button(label=t("boost_reset_sysctl"))
        reset_btn.connect("clicked", self._on_reset_sysctl)
        sys_btn_row.append(apply_btn)
        sys_btn_row.append(reset_btn)
        content.append(sys_btn_row)

        clamp.set_child(content)
        scroller.set_child(clamp)
        self.append(scroller)

        self._refresh_memory()
        self._rebuild_sysctl_group()

    def _refresh_memory(self) -> None:
        snap = read_memory_snapshot()
        self.ram_card.update_metric(
            f"{snap.used_percent:.1f}%",
            snap.used_percent / 100.0,
            f"{format_bytes(snap.used_bytes)} / {format_bytes(snap.total_bytes)} (Cache: {format_bytes(snap.cached_bytes)})",
        )
        self.swap_card.update_metric(
            f"{snap.swap_percent:.1f}%",
            snap.swap_percent / 100.0,
            f"{format_bytes(snap.swap_used_bytes)} / {format_bytes(snap.swap_total_bytes)}",
        )

    def _rebuild_sysctl_group(self) -> None:
        while (child := self.sysctl_box.get_first_child()) is not None:
            self.sysctl_box.remove(child)
        self._sysctl_checks.clear()

        grp = Adw.PreferencesGroup(title=t("boost_sysctl_title"), description=t("boost_sysctl_sub"))
        for spec, cur_val, is_active in get_kernel_tweak_states():
            row = Adw.ActionRow(title=t(spec.title_key), subtitle=t(spec.desc_key))
            chk = Gtk.CheckButton(active=is_active or True)
            chk.set_valign(Gtk.Align.CENTER)
            self._sysctl_checks[spec.tweak_id] = chk
            row.add_prefix(chk)
            row.add_suffix(
                make_badge(
                    f"Current: {cur_val} → {spec.recommended_display}",
                    "badge-cyan" if is_active else "badge-amber",
                )
            )
            grp.add(row)
        self.sysctl_box.append(grp)

    def _on_boost_ram(self, _btn: Gtk.Button) -> None:
        self.ram_btn.set_sensitive(False)
        self._set_status(t("status_working"))

        def worker() -> None:
            ok, freed, msg = boost_ram_memory()
            GLib.idle_add(self._after_ram_boost, ok, freed, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _after_ram_boost(self, ok: bool, freed: int, msg: str) -> bool:
        self.ram_btn.set_sensitive(True)
        self._refresh_memory()
        self._set_status(t("status_ready"))
        if ok:
            self._notify(t("boost_ram_freed", size=format_bytes(freed)))
        else:
            self._notify(msg or "Operation cancelled.")
        return False

    def _on_mode_selected(self, _btn: Gtk.Button, mode_id: str) -> None:
        self._set_status(t("status_working"))

        def worker() -> None:
            ok, msg = apply_turbo_mode(mode_id)
            prof = get_active_power_profile()
            GLib.idle_add(self._after_mode_change, ok, msg, mode_id, prof)

        threading.Thread(target=worker, daemon=True).start()

    def _after_mode_change(self, ok: bool, msg: str, mode_id: str, prof: str) -> bool:
        self._set_status(t("status_ready"))
        self.pwr_row.set_subtitle(prof)
        self._refresh_memory()
        for mid, badge in self._mode_badges.items():
            badge.set_label(t("active") if mid == mode_id else t("inactive"))
            badge.set_css_classes(["badge-cyan" if mid == mode_id else "badge-blue"])
        self._notify(msg if msg else f"Mode: {mode_id}")
        return False

    def _on_apply_sysctl(self, _btn: Gtk.Button) -> None:
        chosen = [tid for tid, chk in self._sysctl_checks.items() if chk.get_active()]
        self._set_status(t("status_working"))

        def worker() -> None:
            ok, msg = apply_selected_kernel_tweaks(chosen)
            GLib.idle_add(self._after_sysctl, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_reset_sysctl(self, _btn: Gtk.Button) -> None:
        self._set_status(t("status_working"))

        def worker() -> None:
            ok, msg = reset_kernel_tweaks()
            GLib.idle_add(self._after_sysctl, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _after_sysctl(self, _ok: bool, msg: str) -> bool:
        self._set_status(t("status_ready"))
        self._rebuild_sysctl_group()
        self._notify(msg.splitlines()[0] if msg else "Updated sysctl.")
        return False
