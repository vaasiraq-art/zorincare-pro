"""Page 3: Driver & Firmware Booster (IObit Driver Booster for Zorin OS 18.1 Pro)."""

from __future__ import annotations

import threading
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from zorincare.core.driver_booster import (
    DriverScanReport,
    install_driver_packages,
    install_recommended_drivers,
    run_driver_scan,
    update_all_firmware,
)
from zorincare.i18n import t
from zorincare.ui.widgets import make_badge


class DriversPage(Gtk.Box):
    def __init__(self, notify_toast: Callable[[str], None], set_status: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._notify = notify_toast
        self._set_status = set_status
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

        # Hero Banner + Action Buttons
        banner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        banner.add_css_class("hero-banner")

        title = Gtk.Label(label=t("drv_headline"), xalign=0.0, wrap=True)
        title.add_css_class("page-title")
        desc = Gtk.Label(label=t("drv_desc"), xalign=0.0, wrap=True)
        desc.add_css_class("dim-caption")

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.scan_btn = Gtk.Button(label=t("drv_scan_btn"))
        self.scan_btn.add_css_class("care-cta-button")
        self.scan_btn.connect("clicked", lambda *_: self._start_scan())

        self.auto_drv_btn = Gtk.Button(label=t("drv_auto_install_btn"))
        self.auto_drv_btn.add_css_class("fix-cta-button")
        self.auto_drv_btn.connect("clicked", self._on_auto_install)

        self.fw_btn = Gtk.Button(label=t("drv_fw_update_btn"))
        self.fw_btn.connect("clicked", self._on_fw_update)

        self.spinner = Gtk.Spinner()
        actions.append(self.scan_btn)
        actions.append(self.auto_drv_btn)
        actions.append(self.fw_btn)
        actions.append(self.spinner)

        banner.append(title)
        banner.append(desc)
        banner.append(actions)
        content.append(banner)

        self.body_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.append(self.body_box)

        clamp.set_child(content)
        scroller.set_child(clamp)
        self.append(scroller)

        GLib.idle_add(self._start_scan)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.scan_btn.set_sensitive(not busy)
        self.auto_drv_btn.set_sensitive(not busy)
        self.fw_btn.set_sensitive(not busy)
        if busy:
            self.spinner.start()
            self._set_status(t("status_working"))
        else:
            self.spinner.stop()
            self._set_status(t("status_ready"))

    def _start_scan(self) -> bool:
        if self._busy:
            return False
        self._set_busy(True)

        def worker() -> None:
            rep = run_driver_scan()
            GLib.idle_add(self._render_report, rep)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _render_report(self, rep: DriverScanReport) -> bool:
        self._set_busy(False)
        while (child := self.body_box.get_first_child()) is not None:
            self.body_box.remove(child)

        # 1. Proprietary Drivers (ubuntu-drivers)
        prop_grp = Adw.PreferencesGroup(title=t("drv_prop_group"))
        if not rep.proprietary_devices:
            prop_grp.add(Adw.ActionRow(title=t("drv_no_prop")))
        else:
            for dev in rep.proprietary_devices:
                exp = Adw.ExpanderRow(
                    title=f"{dev.vendor} — {dev.model}",
                    subtitle=dev.sysfs_path,
                    expanded=True,
                )
                for opt in dev.options:
                    orow = Adw.ActionRow(title=opt.package, subtitle=opt.description)
                    if opt.recommended:
                        orow.add_suffix(make_badge(t("recommended"), "badge-cyan"))
                    if opt.installed:
                        orow.add_suffix(make_badge(t("installed"), "badge-blue"))
                    else:
                        ibtn = Gtk.Button(label=t("drv_install_pkg"), valign=Gtk.Align.CENTER)
                        ibtn.connect("clicked", self._on_install_pkg, [opt.package])
                        orow.add_suffix(ibtn)
                    exp.add_row(orow)
                prop_grp.add(exp)
        self.body_box.append(prop_grp)

        # 2. LVFS Firmware Updates (fwupd)
        fw_grp = Adw.PreferencesGroup(title=t("drv_fw_group"))
        if not rep.firmware_updates:
            fw_grp.add(Adw.ActionRow(title=t("drv_no_fw")))
        else:
            for fw in rep.firmware_updates:
                frow = Adw.ActionRow(
                    title=f"{fw.vendor} {fw.name}".strip(),
                    subtitle=fw.summary,
                )
                frow.add_suffix(make_badge(f"{fw.current_version} → {fw.target_version}", "badge-amber"))
                fw_grp.add(frow)
        self.body_box.append(fw_grp)

        # 3. Kernel, Microcode, Vulkan, DKMS & Codecs Stack
        st = rep.stack
        stack_grp = Adw.PreferencesGroup(title=t("drv_stack_group"))

        krow = Adw.ActionRow(
            title=f"Linux Kernel {st.kernel_version}",
            subtitle="Zorin OS 18.1 Hardware Enablement (HWE) Stack",
        )
        krow.add_suffix(make_badge("Active", "badge-cyan"))
        stack_grp.add(krow)

        mrow = Adw.ActionRow(
            title=f"CPU Microcode ({st.microcode_pkg})",
            subtitle=f"Detected CPU Vendor: {st.cpu_vendor}",
        )
        if st.microcode_installed:
            mrow.add_suffix(make_badge(t("installed"), "badge-cyan"))
        else:
            mbtn = Gtk.Button(label=t("drv_install_pkg"), valign=Gtk.Align.CENTER)
            mbtn.connect("clicked", self._on_install_pkg, [st.microcode_pkg])
            mrow.add_suffix(make_badge(t("not_installed"), "badge-amber"))
            mrow.add_suffix(mbtn)
        stack_grp.add(mrow)

        vrow = Adw.ActionRow(
            title="Mesa Vulkan Graphics Drivers (mesa-vulkan-drivers)",
            subtitle="Required for modern gaming, Proton, and hardware-accelerated apps",
        )
        if st.vulkan_installed:
            vrow.add_suffix(make_badge(t("installed"), "badge-cyan"))
        else:
            vbtn = Gtk.Button(label=t("drv_install_pkg"), valign=Gtk.Align.CENTER)
            vbtn.connect("clicked", self._on_install_pkg, ["mesa-vulkan-drivers", "vulkan-tools"])
            vrow.add_suffix(vbtn)
        stack_grp.add(vrow)

        crow = Adw.ActionRow(
            title=t("drv_codecs_title"),
            subtitle=f"{t('drv_codecs_desc')} ({st.restricted_codecs_pkg})",
        )
        if st.restricted_codecs_installed:
            crow.add_suffix(make_badge(t("installed"), "badge-cyan"))
        else:
            cbtn = Gtk.Button(label=t("drv_install_pkg"), valign=Gtk.Align.CENTER)
            cbtn.connect("clicked", self._on_install_pkg, [st.restricted_codecs_pkg])
            crow.add_suffix(cbtn)
        stack_grp.add(crow)

        if st.dkms_summary:
            dkms_row = Adw.ExpanderRow(
                title="DKMS Kernel Module Status",
                subtitle=f"{len(st.dkms_summary)} module(s) registered",
            )
            dkms_row.add_suffix(
                make_badge(
                    "Warning" if st.dkms_has_warning else "Healthy",
                    "badge-red" if st.dkms_has_warning else "badge-cyan",
                )
            )
            for line in st.dkms_summary:
                dkms_row.add_row(Adw.ActionRow(title=line))
            stack_grp.add(dkms_row)

        self.body_box.append(stack_grp)

        # 4. PCI & USB Hardware Map
        hw_grp = Adw.PreferencesGroup(title=t("drv_hw_group"))
        for pci in rep.pci_devices:
            drv_label = pci.driver_in_use or "none"
            prow = Adw.ActionRow(
                title=pci.device_name,
                subtitle=f"[{pci.slot}] {pci.category}  •  Modules: {pci.kernel_modules or 'built-in'}",
            )
            if pci.missing_driver:
                prow.add_suffix(make_badge("Missing Driver!", "badge-red"))
            else:
                prow.add_suffix(make_badge(f"Driver: {drv_label}", "badge-blue"))
            hw_grp.add(prow)

        if rep.usb_devices:
            usb_exp = Adw.ExpanderRow(
                title="Connected USB Peripherals",
                subtitle=f"{len(rep.usb_devices)} external USB device(s)",
            )
            for u in rep.usb_devices:
                usb_exp.add_row(Adw.ActionRow(title=u))
            hw_grp.add(usb_exp)

        self.body_box.append(hw_grp)
        return False

    def _on_auto_install(self, _btn: Gtk.Button) -> None:
        if self._busy:
            return
        self._set_busy(True)

        def worker() -> None:
            ok, msg = install_recommended_drivers()
            rep = run_driver_scan()
            GLib.idle_add(self._after_action, ok, msg, rep)

        threading.Thread(target=worker, daemon=True).start()

    def _on_install_pkg(self, _btn: Gtk.Button, pkgs: list[str]) -> None:
        if self._busy:
            return
        self._set_busy(True)

        def worker() -> None:
            ok, msg = install_driver_packages(pkgs)
            rep = run_driver_scan()
            GLib.idle_add(self._after_action, ok, msg, rep)

        threading.Thread(target=worker, daemon=True).start()

    def _on_fw_update(self, _btn: Gtk.Button) -> None:
        if self._busy:
            return
        self._set_busy(True)

        def worker() -> None:
            ok, msg = update_all_firmware()
            rep = run_driver_scan()
            GLib.idle_add(self._after_action, ok, msg, rep)

        threading.Thread(target=worker, daemon=True).start()

    def _after_action(self, ok: bool, msg: str, rep: DriverScanReport) -> bool:
        self._render_report(rep)
        summary = "Operation completed successfully." if ok else (msg.splitlines()[-1] if msg else "Failed.")
        self._notify(summary)
        return False
