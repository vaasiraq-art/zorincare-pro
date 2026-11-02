"""GTK 4.14 validated CSS themes: IObit Cyber Dark Neon & Zorin Pro Native."""

from __future__ import annotations

CYBER_DARK_CSS = """
window.zorincare-cyber {
    background-color: #08101E;
    color: #E6F1FF;
}

window.zorincare-cyber headerbar {
    background-image: linear-gradient(90deg, #0A1528, #102342);
    color: #E6F1FF;
    border-bottom: 1px solid #1C355E;
}

.zorincare-sidebar {
    background-color: #0B1629;
    border-right: 1px solid #193056;
    border-left: 1px solid #193056;
}

.zorincare-nav-list {
    background-color: transparent;
    padding: 8px;
}

.zorincare-nav-list row {
    border-radius: 12px;
    margin-bottom: 4px;
    padding: 10px 12px;
    transition: background-color 150ms ease;
}

.zorincare-nav-list row:hover {
    background-color: rgba(0, 187, 249, 0.10);
}

.zorincare-nav-list row:selected {
    background-image: linear-gradient(135deg, rgba(0, 245, 212, 0.20), rgba(0, 187, 249, 0.24));
    border: 1px solid rgba(0, 245, 212, 0.48);
}

.hero-banner {
    background-image: linear-gradient(135deg, #0E1E38, #132A4E);
    border: 1px solid #1F4073;
    border-radius: 18px;
    padding: 20px;
}

.metric-card {
    background-color: #0E1B31;
    border: 1px solid #1B355E;
    border-radius: 14px;
    padding: 16px;
}

.care-cta-button {
    background-image: linear-gradient(135deg, #00F5D4, #00BBF9);
    color: #04101E;
    font-weight: 800;
    font-size: 15px;
    border-radius: 999px;
    padding: 12px 34px;
    border: none;
    box-shadow: 0 4px 16px rgba(0, 245, 212, 0.30);
}

.care-cta-button:hover {
    background-image: linear-gradient(135deg, #48CAE4, #00F5D4);
}

.fix-cta-button {
    background-image: linear-gradient(135deg, #00BBF9, #4361EE);
    color: #FFFFFF;
    font-weight: 800;
    font-size: 15px;
    border-radius: 999px;
    padding: 12px 34px;
    border: none;
    box-shadow: 0 4px 16px rgba(67, 97, 238, 0.38);
}

.danger-pill-btn {
    background-color: rgba(239, 71, 111, 0.18);
    color: #FF6B8B;
    border: 1px solid rgba(239, 71, 111, 0.45);
    border-radius: 10px;
    font-weight: 700;
    padding: 6px 14px;
}

.danger-pill-btn:hover {
    background-color: rgba(239, 71, 111, 0.32);
}

.badge-cyan {
    background-color: rgba(0, 245, 212, 0.16);
    color: #00F5D4;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

.badge-blue {
    background-color: rgba(0, 187, 249, 0.18);
    color: #56CFE1;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

.badge-amber {
    background-color: rgba(255, 183, 3, 0.20);
    color: #FFD166;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

.badge-red {
    background-color: rgba(239, 71, 111, 0.20);
    color: #FF758F;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

.page-title {
    font-size: 22px;
    font-weight: 800;
}

.metric-big {
    font-size: 24px;
    font-weight: 800;
    color: #00F5D4;
}

.dim-caption {
    opacity: 0.72;
    font-size: 12px;
}

.statusbar-strip {
    background-color: #070E1B;
    border-top: 1px solid #162B4D;
    padding: 6px 14px;
    font-size: 12px;
}
"""

ZORIN_NATIVE_CSS = """
.zorincare-nav-list {
    background-color: transparent;
    padding: 8px;
}

.zorincare-nav-list row {
    border-radius: 10px;
    margin-bottom: 4px;
    padding: 10px 12px;
}

.hero-banner {
    background-color: rgba(21, 166, 240, 0.10);
    border: 1px solid rgba(21, 166, 240, 0.28);
    border-radius: 16px;
    padding: 20px;
}

.metric-card {
    background-color: rgba(128, 128, 128, 0.08);
    border: 1px solid rgba(128, 128, 128, 0.18);
    border-radius: 14px;
    padding: 16px;
}

.care-cta-button {
    background-image: linear-gradient(135deg, #15A6F0, #0D74CE);
    color: #FFFFFF;
    font-weight: 800;
    font-size: 15px;
    border-radius: 999px;
    padding: 12px 34px;
    border: none;
}

.fix-cta-button {
    background-image: linear-gradient(135deg, #06D6A0, #118AB2);
    color: #FFFFFF;
    font-weight: 800;
    font-size: 15px;
    border-radius: 999px;
    padding: 12px 34px;
    border: none;
}

.danger-pill-btn {
    background-color: rgba(220, 53, 69, 0.14);
    color: #E03131;
    border: 1px solid rgba(220, 53, 69, 0.35);
    border-radius: 10px;
    font-weight: 700;
    padding: 6px 14px;
}

.badge-cyan {
    background-color: rgba(6, 214, 160, 0.18);
    color: #099268;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

.badge-blue {
    background-color: rgba(21, 166, 240, 0.18);
    color: #15A6F0;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

.badge-amber {
    background-color: rgba(245, 159, 0, 0.18);
    color: #E67700;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

.badge-red {
    background-color: rgba(224, 49, 49, 0.18);
    color: #E03131;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

.page-title {
    font-size: 22px;
    font-weight: 800;
}

.metric-big {
    font-size: 24px;
    font-weight: 800;
    color: #15A6F0;
}

.dim-caption {
    opacity: 0.70;
    font-size: 12px;
}

.statusbar-strip {
    border-top: 1px solid rgba(128, 128, 128, 0.22);
    padding: 6px 14px;
    font-size: 12px;
}
"""
