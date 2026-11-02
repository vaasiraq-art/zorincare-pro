"""Reusable GTK4 / Cairo custom widgets: IObit-style Animated Health Score Ring, Metric Cards & Log Viewer."""

from __future__ import annotations

import math
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from zorincare.core.runner import LOG_BUS
from zorincare.i18n import t


class HealthScoreRing(Gtk.DrawingArea):
    """Animated Cairo radial health gauge inspired by IObit Advanced SystemCare."""

    def __init__(self, size: int = 210) -> None:
        super().__init__()
        self._score: int = 92
        self._scanning: bool = False
        self._angle_offset: float = 0.0
        self._timer_id: int | None = None
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        try:
            self.set_draw_func(self._on_draw)
        except Exception:
            pass

    def set_score(self, score: int) -> None:
        self._score = max(0, min(100, score))
        self.queue_draw()

    def set_scanning(self, active: bool) -> None:
        self._scanning = active
        if active and self._timer_id is None:
            self._timer_id = GLib.timeout_add(40, self._tick_anim)
        elif not active and self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self.queue_draw()

    def _tick_anim(self) -> bool:
        if not self._scanning:
            self._timer_id = None
            return False
        self._angle_offset = (self._angle_offset + 0.14) % (2.0 * math.pi)
        self.queue_draw()
        return True

    def _score_rgb(self) -> tuple[float, float, float]:
        if self._score >= 85:
            return (0.0, 0.96, 0.83)  # Neon Cyan-Emerald
        if self._score >= 65:
            return (1.0, 0.78, 0.20)  # Amber
        return (0.94, 0.28, 0.44)     # Coral Red

    def _on_draw(self, _area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        cx = width / 2.0
        cy = height / 2.0
        radius = min(width, height) / 2.0 - 16.0
        if radius <= 10:
            return

        # Outer subtle halo
        r, g, b = self._score_rgb()
        cr.set_source_rgba(r, g, b, 0.09)
        cr.arc(cx, cy, radius + 6, 0, 2 * math.pi)
        cr.fill()

        # Background track arc (270 degrees)
        start_ang = math.radians(135)
        end_ang = math.radians(405)
        cr.set_line_width(13.0)
        cr.set_line_cap(1)  # CAIRO_LINE_CAP_ROUND
        cr.set_source_rgba(0.45, 0.58, 0.78, 0.20)
        cr.arc(cx, cy, radius, start_ang, end_ang)
        cr.stroke()

        if self._scanning:
            # Rotating scanner arc
            sweep_start = self._angle_offset
            sweep_end = self._angle_offset + math.radians(110)
            cr.set_source_rgba(0.0, 0.85, 0.98, 0.95)
            cr.arc(cx, cy, radius, sweep_start, sweep_end)
            cr.stroke()
        else:
            # Score progress arc
            frac = self._score / 100.0
            val_end = start_ang + (end_ang - start_ang) * frac
            cr.set_source_rgba(r, g, b, 0.96)
            cr.arc(cx, cy, radius, start_ang, val_end)
            cr.stroke()

        # Center score number
        score_txt = "..." if self._scanning else str(self._score)
        cr.select_font_face("Sans", 0, 1)  # Bold
        cr.set_font_size(44.0)
        ext = cr.text_extents(score_txt)
        cr.set_source_rgba(r, g, b, 1.0)
        cr.move_to(cx - ext.width / 2.0 - ext.x_bearing, cy + 4.0)
        cr.show_text(score_txt)

        # Caption below score
        cap = t("care_score_label")
        cr.set_font_size(11.0)
        ext2 = cr.text_extents(cap)
        cr.set_source_rgba(0.75, 0.84, 0.96, 0.85)
        cr.move_to(cx - ext2.width / 2.0 - ext2.x_bearing, cy + 30.0)
        cr.show_text(cap)


def make_badge(text: str, style: str = "badge-blue") -> Gtk.Label:
    lbl = Gtk.Label(label=text)
    lbl.add_css_class(style)
    lbl.set_valign(Gtk.Align.CENTER)
    return lbl


class MetricGaugeCard(Gtk.Box):
    """Compact telemetry card with title, big value, subtitle, and progress bar."""

    def __init__(self, title: str, icon_name: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add_css_class("metric-card")
        self.set_hexpand(True)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        self.title_lbl = Gtk.Label(label=title, xalign=0.0)
        self.title_lbl.add_css_class("dim-caption")
        self.title_lbl.set_hexpand(True)
        top.append(icon)
        top.append(self.title_lbl)

        self.value_lbl = Gtk.Label(label="--", xalign=0.0)
        self.value_lbl.add_css_class("metric-big")

        self.bar = Gtk.ProgressBar()
        self.bar.set_fraction(0.0)

        self.sub_lbl = Gtk.Label(label="", xalign=0.0)
        self.sub_lbl.add_css_class("dim-caption")
        self.sub_lbl.set_ellipsize(3)  # PANGO_ELLIPSIZE_END

        self.append(top)
        self.append(self.value_lbl)
        self.append(self.bar)
        self.append(self.sub_lbl)

    def update_metric(self, value_text: str, fraction: float, subtitle: str = "") -> None:
        self.value_lbl.set_label(value_text)
        self.bar.set_fraction(max(0.0, min(1.0, fraction)))
        self.sub_lbl.set_label(subtitle)


def show_activity_log_dialog(parent: Gtk.Window) -> None:
    win = Gtk.Window(
        title=t("log_drawer_btn"),
        transient_for=parent,
        modal=True,
        default_width=720,
        default_height=440,
    )
    toolbar = Adw.ToolbarView()
    hb = Adw.HeaderBar()
    toolbar.add_top_bar(hb)

    scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
    tv = Gtk.TextView(editable=False, monospace=True, left_margin=12, right_margin=12, top_margin=12, bottom_margin=12)
    buf = tv.get_buffer()
    text = "\n".join(LOG_BUS.entries) or "No commands logged yet."
    buf.set_text(text)
    scroller.set_child(tv)

    toolbar.set_content(scroller)
    win.set_content(toolbar)
    win.present()
