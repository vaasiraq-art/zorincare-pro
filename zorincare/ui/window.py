"""Main ZorinCare Pro ApplicationWindow with EN/AR RTL live switching and Cyber/Native theming."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from zorincare import APP_VERSION
from zorincare.core.distro import detect_system_profile
from zorincare.i18n import SETTINGS, t
from zorincare.ui.pages.booster_page import BoosterPage
from zorincare.ui.pages.care_page import CarePage
from zorincare.ui.pages.control_page import ControlPage
from zorincare.ui.pages.drivers_page import DriversPage
from zorincare.ui.pages.security_page import SecurityPage
from zorincare.ui.pages.uninstaller_page import UninstallerPage
from zorincare.ui.theme import CYBER_DARK_CSS, ZORIN_NATIVE_CSS
from zorincare.ui.widgets import make_badge, show_activity_log_dialog


NAV_ITEMS = [
    ("care", "nav_care", "nav_care_sub", "emblem-ok-symbolic"),
    ("booster", "nav_booster", "nav_booster_sub", "utilities-system-monitor-symbolic"),
    ("drivers", "nav_drivers", "nav_drivers_sub", "preferences-desktop-display-symbolic"),
    ("uninstaller", "nav_uninstaller", "nav_uninstaller_sub", "user-trash-symbolic"),
    ("control", "nav_control", "nav_control_sub", "preferences-system-symbolic"),
    ("security", "nav_security", "nav_security_sub", "security-high-symbolic"),
]


class ZorinCareWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, default_width=1220, default_height=780)
        self.set_size_request(920, 600)

        self._css_provider = Gtk.CssProvider()
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display,
                self._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        self._active_page_key = "care"
        self._control_page_ref: ControlPage | None = None

        self._apply_direction_and_theme()
        self._build_shell()

    def _apply_direction_and_theme(self) -> None:
        Gtk.Widget.set_default_direction(
            Gtk.TextDirection.RTL if SETTINGS.is_rtl else Gtk.TextDirection.LTR
        )
        theme_mode = SETTINGS.get("theme", "cyber_dark")
        style_mgr = Adw.StyleManager.get_default()

        if theme_mode == "cyber_dark":
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            self.add_css_class("zorincare-cyber")
            css_text = CYBER_DARK_CSS
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)
            self.remove_css_class("zorincare-cyber")
            css_text = ZORIN_NATIVE_CSS

        try:
            self._css_provider.load_from_string(css_text)
        except AttributeError:
            self._css_provider.load_from_data(css_text.encode("utf-8"))

    def _build_shell(self) -> None:
        if self._control_page_ref is not None:
            self._control_page_ref.cleanup()
            self._control_page_ref = None

        self.set_title(t("app_title"))

        self.toast_overlay = Adw.ToastOverlay()
        outer_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # NavigationSplitView (Sidebar + Content Page)
        split = Adw.NavigationSplitView(hexpand=True, vexpand=True)
        split.set_min_sidebar_width(255)
        split.set_max_sidebar_width(290)

        # --- Sidebar ---
        sidebar_toolbar = Adw.ToolbarView()
        sb_header = Adw.HeaderBar()
        sb_title = Gtk.Label(label=f"ZorinCare Pro v{APP_VERSION}")
        sb_title.add_css_class("heading")
        sb_header.set_title_widget(sb_title)
        sidebar_toolbar.add_top_bar(sb_header)

        sb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sb_box.add_css_class("zorincare-sidebar")

        self.nav_list = Gtk.ListBox()
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.add_css_class("zorincare-nav-list")
        self.nav_list.set_vexpand(True)

        self._row_keys: list[str] = []
        selected_idx = 0

        for idx, (pkey, title_k, sub_k, icon_name) in enumerate(NAV_ITEMS):
            row = Gtk.ListBoxRow()
            rbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            ic = Gtk.Image.new_from_icon_name(icon_name)
            ic.set_pixel_size(20)

            tbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            tl = Gtk.Label(label=t(title_k), xalign=0.0)
            tl.add_css_class("heading")
            sl = Gtk.Label(label=t(sub_k), xalign=0.0)
            sl.add_css_class("dim-caption")
            sl.set_ellipsize(3)
            tbox.append(tl)
            tbox.append(sl)

            rbox.append(ic)
            rbox.append(tbox)
            row.set_child(rbox)
            self.nav_list.append(row)
            self._row_keys.append(pkey)
            if pkey == self._active_page_key:
                selected_idx = idx

        self.nav_list.connect("row-selected", self._on_nav_row_selected)
        sb_box.append(self.nav_list)

        # OS Badge Footer in Sidebar
        prof = detect_system_profile()
        os_footer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_start=14,
            margin_end=14,
            margin_top=8,
            margin_bottom=14,
        )
        os_badge = make_badge(prof.distro_name[:30], "badge-cyan")
        os_badge.set_halign(Gtk.Align.START)
        kern_lbl = Gtk.Label(label=f"Kernel {prof.kernel}", xalign=0.0)
        kern_lbl.add_css_class("dim-caption")
        os_footer.append(os_badge)
        os_footer.append(kern_lbl)
        sb_box.append(os_footer)

        sidebar_toolbar.set_content(sb_box)
        sidebar_page = Adw.NavigationPage.new(sidebar_toolbar, t("app_title"))
        split.set_sidebar(sidebar_page)

        # --- Main Content Pane ---
        content_toolbar = Adw.ToolbarView()
        main_hb = Adw.HeaderBar()

        # Language Switcher Button (EN <-> العربية)
        lang_btn = Gtk.Button(label=t("lang_switch_btn"))
        lang_btn.set_tooltip_text(t("lang_toggle_tip"))
        lang_btn.connect("clicked", self._on_toggle_language)
        main_hb.pack_end(lang_btn)

        # Theme Switcher Button (Cyber Neon <-> Zorin Native)
        cur_theme = SETTINGS.get("theme", "cyber_dark")
        theme_lbl = t("theme_native") if cur_theme == "cyber_dark" else t("theme_cyber")
        theme_btn = Gtk.Button(label=theme_lbl)
        theme_btn.set_tooltip_text(t("theme_toggle_tip"))
        theme_btn.connect("clicked", self._on_toggle_theme)
        main_hb.pack_end(theme_btn)

        # Activity Log Button
        log_btn = Gtk.Button(label=t("log_drawer_btn"))
        log_btn.connect("clicked", lambda *_: show_activity_log_dialog(self))
        main_hb.pack_start(log_btn)

        content_toolbar.add_top_bar(main_hb)

        self.page_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=160,
            hexpand=True,
            vexpand=True,
        )

        # Status Bar Strip (created before pages so set_status works immediately)
        status_strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_strip.add_css_class("statusbar-strip")
        self.status_lbl = Gtk.Label(label=t("status_ready"), xalign=0.0, hexpand=True)
        status_strip.append(self.status_lbl)

        # Instantiate all 6 feature pages
        self.page_stack.add_named(CarePage(self.notify_toast, self.set_status), "care")
        self.page_stack.add_named(BoosterPage(self.notify_toast, self.set_status), "booster")
        self.page_stack.add_named(DriversPage(self.notify_toast, self.set_status), "drivers")
        self.page_stack.add_named(UninstallerPage(self, self.notify_toast, self.set_status), "uninstaller")
        ctrl_page = ControlPage(self.notify_toast, self.set_status)
        self._control_page_ref = ctrl_page
        self.page_stack.add_named(ctrl_page, "control")
        self.page_stack.add_named(SecurityPage(self.notify_toast, self.set_status), "security")

        content_toolbar.set_content(self.page_stack)
        content_page = Adw.NavigationPage.new(content_toolbar, t("app_subtitle"))
        split.set_content(content_page)

        outer_vbox.append(split)
        outer_vbox.append(status_strip)
        self.toast_overlay.set_child(outer_vbox)
        self.set_content(self.toast_overlay)

        # Restore active navigation row
        target_row = self.nav_list.get_row_at_index(selected_idx)
        if target_row is not None:
            self.nav_list.select_row(target_row)
        self.page_stack.set_visible_child_name(self._active_page_key)

    def _on_nav_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        idx = row.get_index()
        if 0 <= idx < len(self._row_keys):
            key = self._row_keys[idx]
            self._active_page_key = key
            self.page_stack.set_visible_child_name(key)

    def _on_toggle_language(self, _btn: Gtk.Button) -> None:
        SETTINGS.toggle_lang()
        self._apply_direction_and_theme()
        self._build_shell()

    def _on_toggle_theme(self, _btn: Gtk.Button) -> None:
        cur = SETTINGS.get("theme", "cyber_dark")
        SETTINGS.set("theme", "zorin_native" if cur == "cyber_dark" else "cyber_dark")
        self._apply_direction_and_theme()
        self._build_shell()

    def notify_toast(self, message: str) -> None:
        toast = Adw.Toast.new(message)
        toast.set_timeout(4)
        self.toast_overlay.add_toast(toast)

    def set_status(self, message: str) -> None:
        self.status_lbl.set_label(message)
