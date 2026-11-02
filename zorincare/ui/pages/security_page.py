"""Page 6: Security & Privacy Shield (UFW Firewall, Port Auditor, Privacy Sweep & Security Hardening)."""

from __future__ import annotations

import threading
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from zorincare.core.security_privacy import (
    ListeningPort,
    PrivacyTarget,
    SecurityAuditCheck,
    clean_privacy_traces,
    get_ufw_enabled_status,
    list_listening_ports,
    run_security_audit,
    scan_privacy_traces,
    set_ufw_state,
)
from zorincare.i18n import format_bytes, t
from zorincare.ui.widgets import make_badge


class SecurityPage(Gtk.Box):
    def __init__(self, notify_toast: Callable[[str], None], set_status: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._notify = notify_toast
        self._set_status = set_status
        self._priv_checks: dict[str, Gtk.CheckButton] = {}

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

        banner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        banner.add_css_class("hero-banner")
        title = Gtk.Label(label=t("sec_headline"), xalign=0.0, wrap=True)
        title.add_css_class("page-title")
        desc = Gtk.Label(label=t("sec_desc"), xalign=0.0, wrap=True)
        desc.add_css_class("dim-caption")
        ref_btn = Gtk.Button(label=t("refresh"), halign=Gtk.Align.START)
        ref_btn.connect("clicked", lambda *_: self._refresh_all())
        banner.append(title)
        banner.append(desc)
        banner.append(ref_btn)
        content.append(banner)

        self.body_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.append(self.body_box)

        clamp.set_child(content)
        scroller.set_child(clamp)
        self.append(scroller)

        GLib.idle_add(self._refresh_all)

    def _refresh_all(self) -> bool:
        def worker() -> None:
            ufw = get_ufw_enabled_status()
            audit = run_security_audit()
            priv = scan_privacy_traces()
            ports = list_listening_ports()
            GLib.idle_add(self._render_all, ufw, audit, priv, ports)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _render_all(
        self,
        ufw: tuple[bool, bool, str],
        audit: list[SecurityAuditCheck],
        priv: list[PrivacyTarget],
        ports: list[ListeningPort],
    ) -> bool:
        while (child := self.body_box.get_first_child()) is not None:
            self.body_box.remove(child)
        self._priv_checks.clear()

        ufw_inst, ufw_en, ufw_detail = ufw

        # 1. UFW Firewall Group
        ufw_grp = Adw.PreferencesGroup(title=t("sec_ufw_group"))
        urow = Adw.ActionRow(title="UFW (Uncomplicated Firewall)", subtitle=ufw_detail)
        urow.add_prefix(Gtk.Image.new_from_icon_name("security-high-symbolic"))
        urow.add_suffix(
            make_badge(
                t("enabled") if ufw_en else t("disabled"),
                "badge-cyan" if ufw_en else "badge-red",
            )
        )
        if ufw_inst:
            ubtn = Gtk.Button(
                label=t("sec_ufw_disable") if ufw_en else t("sec_ufw_enable"),
                valign=Gtk.Align.CENTER,
            )
            if not ufw_en:
                ubtn.add_css_class("care-cta-button")
            ubtn.connect("clicked", self._on_toggle_ufw, not ufw_en)
            urow.add_suffix(ubtn)
        ufw_grp.add(urow)
        self.body_box.append(ufw_grp)

        # 2. Privacy & Browser Trace Cleaner
        priv_grp = Adw.PreferencesGroup(title=t("sec_privacy_group"))
        for pt in priv:
            prow = Adw.ActionRow(
                title=t(pt.title_key),
                subtitle=f"{pt.items_count} item(s)",
            )
            chk = Gtk.CheckButton(active=pt.selected, valign=Gtk.Align.CENTER)
            self._priv_checks[pt.target_id] = chk
            prow.add_prefix(chk)
            prow.add_suffix(make_badge(format_bytes(pt.size_bytes), "badge-blue"))
            priv_grp.add(prow)

        sweep_btn = Gtk.Button(label=t("sec_clean_privacy_btn"), halign=Gtk.Align.START)
        sweep_btn.add_css_class("fix-cta-button")
        sweep_btn.connect("clicked", self._on_sweep_privacy)
        self.body_box.append(priv_grp)
        self.body_box.append(sweep_btn)

        # 3. Security Hardening Audit
        aud_grp = Adw.PreferencesGroup(title=t("sec_audit_group"))
        for chk_item in audit:
            arow = Adw.ActionRow(title=chk_item.title, subtitle=chk_item.detail)
            arow.add_suffix(
                make_badge(
                    "PASS" if chk_item.passed else "ATTENTION",
                    "badge-cyan" if chk_item.passed else "badge-amber",
                )
            )
            aud_grp.add(arow)
        self.body_box.append(aud_grp)

        # 4. Open Listening Ports
        port_grp = Adw.PreferencesGroup(title=t("sec_ports_group"))
        if not ports:
            port_grp.add(Adw.ActionRow(title="No externally exposed listening sockets found."))
        else:
            for lp in ports[:40]:
                lrow = Adw.ActionRow(
                    title=f"{lp.proto} Port {lp.port} ({lp.local_address})",
                    subtitle=lp.process_info,
                )
                lrow.add_suffix(make_badge(lp.proto, "badge-blue"))
                port_grp.add(lrow)
        self.body_box.append(port_grp)
        return False

    def _on_toggle_ufw(self, _btn: Gtk.Button, enable: bool) -> None:
        self._set_status(t("status_working"))

        def worker() -> None:
            _ok, msg = set_ufw_state(enable)
            GLib.idle_add(self._after_ufw, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _after_ufw(self, msg: str) -> bool:
        self._set_status(t("status_ready"))
        self._notify(msg.splitlines()[0] if msg else "Firewall updated.")
        self._refresh_all()
        return False

    def _on_sweep_privacy(self, _btn: Gtk.Button) -> None:
        chosen = [ pid for pid, chk in self._priv_checks.items() if chk.get_active() ]
        if not chosen:
            return
        self._set_status(t("status_working"))

        def worker() -> None:
            freed = clean_privacy_traces(chosen)
            GLib.idle_add(self._after_sweep, freed)

        threading.Thread(target=worker, daemon=True).start()

    def _after_sweep(self, freed: int) -> bool:
        self._set_status(t("status_ready"))
        self._notify(f"Privacy sweep complete — cleared {format_bytes(freed)}!")
        self._refresh_all()
        return False
