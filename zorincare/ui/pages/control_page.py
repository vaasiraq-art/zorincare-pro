"""Page 5: Full PC Control Center (Live Monitor, Process Killer, Startup/Services, DNS/Power/Zorin Tweaks & Disk Analyzer)."""

from __future__ import annotations

import threading
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from zorincare.core.distro import detect_system_profile
from zorincare.core.pc_control import (
    AutostartItem,
    DiskSpaceItem,
    LiveTelemetryPoller,
    ProcessInfo,
    SystemdServiceItem,
    analyze_home_disk_space,
    control_systemd_service,
    flush_dns_cache,
    get_zorin_desktop_tweaks,
    list_autostart_entries,
    list_processes,
    list_systemd_services,
    schedule_power_shutdown,
    set_autostart_enabled,
    set_zorin_desktop_tweak,
    switch_dns_preset,
    terminate_process,
)
from zorincare.i18n import format_bytes, t
from zorincare.ui.widgets import MetricGaugeCard, make_badge


class ControlPage(Gtk.Box):
    def __init__(self, notify_toast: Callable[[str], None], set_status: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._notify = notify_toast
        self._set_status = set_status
        self._poller = LiveTelemetryPoller()
        self._procs: list[ProcessInfo] = []
        self._timer_id: int | None = None

        # Top sub-tab switcher bar
        switcher_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            margin_top=12,
            margin_bottom=4,
        )
        self.stack = Adw.ViewStack(hexpand=True, vexpand=True)
        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        switcher_bar.append(switcher)
        self.append(switcher_bar)
        self.append(self.stack)

        # Build 5 sub-tabs
        self.stack.add_titled_with_icon(
            self._build_monitor_tab(),
            "monitor",
            t("ctrl_tab_monitor"),
            "utilities-system-monitor-symbolic",
        )
        self.stack.add_titled_with_icon(
            self._build_processes_tab(),
            "processes",
            t("ctrl_tab_processes"),
            "system-run-symbolic",
        )
        self.stack.add_titled_with_icon(
            self._build_services_tab(),
            "services",
            t("ctrl_tab_services"),
            "emblem-system-symbolic",
        )
        self.stack.add_titled_with_icon(
            self._build_tools_tab(),
            "tools",
            t("ctrl_tab_tools"),
            "preferences-system-symbolic",
        )
        self.stack.add_titled_with_icon(
            self._build_disk_tab(),
            "disk",
            t("ctrl_tab_disk"),
            "drive-harddisk-symbolic",
        )

        # Start live 1.5s hardware telemetry loop
        self._tick_telemetry()
        self._timer_id = GLib.timeout_add(1500, self._tick_telemetry)

    def cleanup(self) -> None:
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    # --- Tab 1: Live Monitor ---
    def _build_monitor_tab(self) -> Gtk.Widget:
        sc = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        clamp = Adw.Clamp(maximum_size=960)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_top=16,
            margin_bottom=24,
            margin_start=20,
            margin_end=20,
        )

        banner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        banner.add_css_class("hero-banner")
        prof = detect_system_profile()
        t_lbl = Gtk.Label(label=f"{prof.distro_name} ({prof.hostname})", xalign=0.0, wrap=True)
        t_lbl.add_css_class("page-title")
        s_lbl = Gtk.Label(
            label=f"Kernel {prof.kernel}  •  {prof.desktop} ({prof.session_type})  •  {prof.cpu_model} ({prof.cpu_cores} threads)",
            xalign=0.0,
            wrap=True,
        )
        s_lbl.add_css_class("dim-caption")
        banner.append(t_lbl)
        banner.append(s_lbl)
        box.append(banner)

        grid1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, homogeneous=True)
        self.cpu_card = MetricGaugeCard(t("ctrl_cpu"), "processor-symbolic")
        self.ram_card = MetricGaugeCard(t("ctrl_ram"), "drive-multidisk-symbolic")
        self.temp_card = MetricGaugeCard(t("ctrl_temp"), "weather-clear-symbolic")
        grid1.append(self.cpu_card)
        grid1.append(self.ram_card)
        grid1.append(self.temp_card)
        box.append(grid1)

        grid2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, homogeneous=True)
        self.swap_card = MetricGaugeCard(t("ctrl_swap"), "media-flash-symbolic")
        self.net_card = MetricGaugeCard(t("ctrl_net"), "network-transmit-receive-symbolic")
        self.disk_card = MetricGaugeCard(t("ctrl_disk_root"), "drive-harddisk-symbolic")
        grid2.append(self.swap_card)
        grid2.append(self.net_card)
        grid2.append(self.disk_card)
        box.append(grid2)

        self.uptime_lbl = Gtk.Label(label="", xalign=0.0)
        self.uptime_lbl.add_css_class("dim-caption")
        box.append(self.uptime_lbl)

        clamp.set_child(box)
        sc.set_child(clamp)
        return sc

    def _tick_telemetry(self) -> bool:
        s = self._poller.sample()
        freq_txt = f"{s.cpu_freq_mhz} MHz" if s.cpu_freq_mhz else "Live"
        self.cpu_card.update_metric(f"{s.cpu_percent:.1f}%", s.cpu_percent / 100.0, freq_txt)
        self.ram_card.update_metric(
            f"{s.memory.used_percent:.1f}%",
            s.memory.used_percent / 100.0,
            f"{format_bytes(s.memory.used_bytes)} / {format_bytes(s.memory.total_bytes)}",
        )
        if s.temp_celsius is not None:
            self.temp_card.update_metric(
                f"{s.temp_celsius:.1f} °C",
                min(1.0, s.temp_celsius / 100.0),
                "Normal Thermal Zone" if s.temp_celsius < 80 else "High Load Temperature",
            )
        else:
            self.temp_card.update_metric("N/A", 0.0, "No hwmon thermal sensor exposed")

        self.swap_card.update_metric(
            f"{s.memory.swap_percent:.1f}%",
            s.memory.swap_percent / 100.0,
            f"{format_bytes(s.memory.swap_used_bytes)} / {format_bytes(s.memory.swap_total_bytes)}",
        )
        net_total = s.net_down_bps + s.net_up_bps
        self.net_card.update_metric(
            f"↓ {format_bytes(s.net_down_bps)}/s",
            min(1.0, net_total / (25 * 1024 * 1024)),
            f"↑ {format_bytes(s.net_up_bps)}/s",
        )
        d_frac = s.root_used_bytes / max(1, s.root_total_bytes)
        self.disk_card.update_metric(
            f"{d_frac * 100.0:.1f}%",
            d_frac,
            f"{format_bytes(s.root_used_bytes)} / {format_bytes(s.root_total_bytes)}",
        )

        hrs = s.uptime_seconds // 3600
        mins = (s.uptime_seconds % 3600) // 60
        bat_part = (
            f"  •  Battery: {s.battery_percent}% ({'Charging' if s.battery_charging else 'Discharging'})"
            if s.battery_percent is not None
            else ""
        )
        self.uptime_lbl.set_label(f"System Uptime: {hrs}h {mins}m{bat_part}")
        return True

    # --- Tab 2: Task Manager ---
    def _build_processes_tab(self) -> Gtk.Widget:
        sc = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        clamp = Adw.Clamp(maximum_size=960)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=16,
            margin_bottom=24,
            margin_start=20,
            margin_end=20,
        )

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.proc_search = Gtk.SearchEntry(placeholder_text=t("ctrl_proc_search"), hexpand=True)
        self.proc_search.connect("search-changed", lambda *_: self._render_procs())
        ref_btn = Gtk.Button(label=t("refresh"))
        ref_btn.connect("clicked", lambda *_: self._load_procs())
        bar.append(self.proc_search)
        bar.append(ref_btn)
        box.append(bar)

        self.proc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.append(self.proc_box)

        clamp.set_child(box)
        sc.set_child(clamp)
        GLib.idle_add(self._load_procs)
        return sc

    def _load_procs(self) -> bool:
        def worker() -> None:
            procs = list_processes(limit=75)
            GLib.idle_add(self._set_procs, procs)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _set_procs(self, procs: list[ProcessInfo]) -> bool:
        self._procs = procs
        self._render_procs()
        return False

    def _render_procs(self) -> None:
        while (child := self.proc_box.get_first_child()) is not None:
            self.proc_box.remove(child)

        q = self.proc_search.get_text().strip().lower()
        filtered = [
            p for p in self._procs if not q or q in p.name.lower() or q in str(p.pid)
        ]

        grp = Adw.PreferencesGroup(title=f"Top Active Processes ({len(filtered)})")
        for p in filtered[:60]:
            row = Adw.ActionRow(
                title=f"{p.name} (PID {p.pid})",
                subtitle=f"User: {p.user}  •  RAM: {format_bytes(p.ram_bytes)}",
            )
            row.add_suffix(make_badge(f"CPU {p.cpu_percent:.1f}%", "badge-cyan" if p.cpu_percent < 40 else "badge-amber"))
            if not p.protected:
                end_btn = Gtk.Button(label=t("ctrl_kill_btn"), valign=Gtk.Align.CENTER)
                end_btn.connect("clicked", self._on_kill_proc, p, False)
                fkill_btn = Gtk.Button(label=t("ctrl_force_kill_btn"), valign=Gtk.Align.CENTER)
                fkill_btn.add_css_class("danger-pill-btn")
                fkill_btn.connect("clicked", self._on_kill_proc, p, True)
                row.add_suffix(end_btn)
                row.add_suffix(fkill_btn)
            else:
                row.add_suffix(make_badge("System", "badge-blue"))
            grp.add(row)
        self.proc_box.append(grp)

    def _on_kill_proc(self, _btn: Gtk.Button, proc: ProcessInfo, force: bool) -> None:
        ok, msg = terminate_process(proc.pid, proc.name, force=force)
        self._notify(msg)
        if ok:
            self._load_procs()

    # --- Tab 3: Startup & Services ---
    def _build_services_tab(self) -> Gtk.Widget:
        sc = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        clamp = Adw.Clamp(maximum_size=960)
        self.svc_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_top=16,
            margin_bottom=24,
            margin_start=20,
            margin_end=20,
        )
        ref_btn = Gtk.Button(label=t("refresh"), halign=Gtk.Align.START)
        ref_btn.connect("clicked", lambda *_: self._load_startup_and_services())
        self.svc_container.append(ref_btn)

        self.svc_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.svc_container.append(self.svc_inner)

        clamp.set_child(self.svc_container)
        sc.set_child(clamp)
        GLib.idle_add(self._load_startup_and_services)
        return sc

    def _load_startup_and_services(self) -> bool:
        def worker() -> None:
            auto = list_autostart_entries()
            svcs = list_systemd_services(limit=60)
            GLib.idle_add(self._render_startup_and_services, auto, svcs)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _render_startup_and_services(
        self,
        autostarts: list[AutostartItem],
        services: list[SystemdServiceItem],
    ) -> bool:
        while (child := self.svc_inner.get_first_child()) is not None:
            self.svc_inner.remove(child)

        auto_grp = Adw.PreferencesGroup(title=t("ctrl_autostart_group"))
        if not autostarts:
            auto_grp.add(Adw.ActionRow(title="No startup entries configured."))
        else:
            for item in autostarts:
                row = Adw.ActionRow(title=item.name, subtitle=item.comment or item.exec_cmd)
                sw = Gtk.Switch(active=item.enabled, valign=Gtk.Align.CENTER)
                sw.connect("state-set", self._on_autostart_toggled, item)
                row.add_suffix(sw)
                auto_grp.add(row)
        self.svc_inner.append(auto_grp)

        svc_grp = Adw.PreferencesGroup(title=t("ctrl_systemd_group"))
        for svc in services:
            row = Adw.ActionRow(title=svc.unit, subtitle=svc.description)
            is_running = svc.active_state == "active"
            row.add_suffix(
                make_badge(
                    f"{svc.active_state} ({svc.sub_state})",
                    "badge-cyan" if is_running else "badge-amber",
                )
            )
            restart_btn = Gtk.Button(label="Restart", valign=Gtk.Align.CENTER)
            restart_btn.connect("clicked", self._on_svc_op, svc.unit, "restart")
            toggle_op = "stop" if is_running else "start"
            toggle_btn = Gtk.Button(label=toggle_op.title(), valign=Gtk.Align.CENTER)
            toggle_btn.connect("clicked", self._on_svc_op, svc.unit, toggle_op)
            row.add_suffix(toggle_btn)
            row.add_suffix(restart_btn)
            svc_grp.add(row)
        self.svc_inner.append(svc_grp)
        return False

    def _on_autostart_toggled(self, _sw: Gtk.Switch, state: bool, item: AutostartItem) -> bool:
        ok = set_autostart_enabled(item, state)
        if not ok:
            self._notify(f"Failed updating {item.name}")
        return False

    def _on_svc_op(self, _btn: Gtk.Button, unit: str, op: str) -> None:
        self._set_status(t("status_working"))

        def worker() -> None:
            ok, msg = control_systemd_service(unit, op)
            GLib.idle_add(self._after_svc_op, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _after_svc_op(self, ok: bool, msg: str) -> bool:
        self._set_status(t("status_ready"))
        self._notify(msg.splitlines()[0] if msg else ("Done" if ok else "Failed"))
        self._load_startup_and_services()
        return False

    # --- Tab 4: System, DNS, Power & Zorin Tweaks ---
    def _build_tools_tab(self) -> Gtk.Widget:
        sc = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        clamp = Adw.Clamp(maximum_size=940)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=16,
            margin_bottom=24,
            margin_start=20,
            margin_end=20,
        )

        # DNS Switcher
        dns_grp = Adw.PreferencesGroup(title=t("ctrl_dns_group"))
        for preset, key in [
            ("auto", "ctrl_dns_auto"),
            ("cloudflare", "ctrl_dns_cf"),
            ("google", "ctrl_dns_google"),
            ("quad9", "ctrl_dns_quad9"),
        ]:
            drow = Adw.ActionRow(title=t(key))
            dbtn = Gtk.Button(label=t("apply"), valign=Gtk.Align.CENTER)
            dbtn.connect("clicked", self._on_dns_preset, preset)
            drow.add_suffix(dbtn)
            dns_grp.add(drow)

        flush_row = Adw.ActionRow(title=t("ctrl_flush_dns"))
        fbtn = Gtk.Button(label=t("ctrl_flush_dns"), valign=Gtk.Align.CENTER)
        fbtn.connect("clicked", self._on_flush_dns)
        flush_row.add_suffix(fbtn)
        dns_grp.add(flush_row)
        box.append(dns_grp)

        # Power Scheduler
        pwr_grp = Adw.PreferencesGroup(title=t("ctrl_power_group"))
        pwr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin_top=6, margin_bottom=6)
        for mins, lkey in [
            (15, "ctrl_shutdown_15"),
            (30, "ctrl_shutdown_30"),
            (60, "ctrl_shutdown_60"),
            (120, "ctrl_shutdown_120"),
            (None, "ctrl_shutdown_cancel"),
        ]:
            b = Gtk.Button(label=t(lkey))
            if mins is None:
                b.add_css_class("danger-pill-btn")
            b.connect("clicked", self._on_power_sched, mins)
            pwr_box.append(b)
        pwr_row = Adw.ActionRow(title=t("ctrl_power_group"))
        pwr_row.add_suffix(pwr_box)
        pwr_grp.add(pwr_row)
        box.append(pwr_grp)

        # Zorin OS / GNOME 46 Desktop Tweaks
        zorin_grp = Adw.PreferencesGroup(title=t("ctrl_zorin_group"))
        for tw in get_zorin_desktop_tweaks():
            zrow = Adw.ActionRow(title=t(tw.title_key), subtitle=f"{tw.schema} → {tw.key}")
            zsw = Gtk.Switch(active=tw.enabled, sensitive=tw.available, valign=Gtk.Align.CENTER)
            zsw.connect("state-set", self._on_zorin_tweak, tw.schema, tw.key)
            zrow.add_suffix(zsw)
            zorin_grp.add(zrow)
        box.append(zorin_grp)

        clamp.set_child(box)
        sc.set_child(clamp)
        return sc

    def _on_dns_preset(self, _btn: Gtk.Button, preset: str) -> None:
        def worker() -> None:
            ok, msg = switch_dns_preset(preset)
            GLib.idle_add(lambda: (self._notify(msg or f"DNS: {preset}"), False)[1])

        threading.Thread(target=worker, daemon=True).start()

    def _on_flush_dns(self, _btn: Gtk.Button) -> None:
        def worker() -> None:
            _ok, msg = flush_dns_cache()
            GLib.idle_add(lambda: (self._notify(msg), False)[1])

        threading.Thread(target=worker, daemon=True).start()

    def _on_power_sched(self, _btn: Gtk.Button, mins: int | None) -> None:
        def worker() -> None:
            _ok, msg = schedule_power_shutdown(mins)
            GLib.idle_add(lambda: (self._notify(msg), False)[1])

        threading.Thread(target=worker, daemon=True).start()

    def _on_zorin_tweak(self, _sw: Gtk.Switch, state: bool, schema: str, key: str) -> bool:
        set_zorin_desktop_tweak(schema, key, state)
        return False

    # --- Tab 5: Disk Space Analyzer ---
    def _build_disk_tab(self) -> Gtk.Widget:
        sc = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        clamp = Adw.Clamp(maximum_size=940)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=16,
            margin_bottom=24,
            margin_start=20,
            margin_end=20,
        )

        scan_btn = Gtk.Button(label=t("ctrl_disk_scan_btn"), halign=Gtk.Align.START)
        scan_btn.add_css_class("care-cta-button")
        scan_btn.connect("clicked", self._on_scan_disk)
        box.append(scan_btn)

        self.disk_results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(self.disk_results_box)

        clamp.set_child(box)
        sc.set_child(clamp)
        return sc

    def _on_scan_disk(self, btn: Gtk.Button) -> None:
        btn.set_sensitive(False)
        self._set_status(t("status_working"))

        def worker() -> None:
            items = analyze_home_disk_space()
            GLib.idle_add(self._render_disk_items, btn, items)

        threading.Thread(target=worker, daemon=True).start()

    def _render_disk_items(self, btn: Gtk.Button, items: list[DiskSpaceItem]) -> bool:
        btn.set_sensitive(True)
        self._set_status(t("status_ready"))
        while (child := self.disk_results_box.get_first_child()) is not None:
            self.disk_results_box.remove(child)

        grp = Adw.PreferencesGroup(title="Largest Directories & Files in Home (~/)")
        max_sz = max((i.size_bytes for i in items), default=1)
        for it in items:
            row = Adw.ActionRow(title=it.path, subtitle="Directory" if it.is_dir else "File")
            bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER)
            bar.set_size_request(140, -1)
            bar.set_fraction(min(1.0, it.size_bytes / max(1, max_sz)))
            row.add_suffix(bar)
            row.add_suffix(make_badge(format_bytes(it.size_bytes), "badge-cyan"))
            grp.add(row)
        self.disk_results_box.append(grp)
        return False
