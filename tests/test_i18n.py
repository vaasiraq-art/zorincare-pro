"""Tests for English + Arabic (RTL) translation completeness and formatting."""

from __future__ import annotations

import re
import unittest

from zorincare.i18n import SETTINGS, TRANSLATIONS, format_bytes, t


PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


class TestI18n(unittest.TestCase):
    def test_en_and_ar_keys_match_exactly(self) -> None:
        en_keys = set(TRANSLATIONS["en"].keys())
        ar_keys = set(TRANSLATIONS["ar"].keys())
        missing_in_ar = en_keys - ar_keys
        missing_in_en = ar_keys - en_keys
        self.assertEqual(missing_in_ar, set(), f"Missing Arabic keys: {missing_in_ar}")
        self.assertEqual(missing_in_en, set(), f"Extra Arabic keys missing in English: {missing_in_en}")

    def test_placeholders_match_across_languages(self) -> None:
        for key, en_val in TRANSLATIONS["en"].items():
            ar_val = TRANSLATIONS["ar"][key]
            en_ph = set(PLACEHOLDER_RE.findall(en_val))
            ar_ph = set(PLACEHOLDER_RE.findall(ar_val))
            self.assertEqual(
                en_ph,
                ar_ph,
                f"Mismatched placeholders for '{key}': EN={en_ph} vs AR={ar_ph}",
            )

    def test_language_toggle_and_rtl(self) -> None:
        orig = SETTINGS.lang
        try:
            SETTINGS.lang = "en"
            self.assertFalse(SETTINGS.is_rtl)
            self.assertEqual(t("care_scan_now"), "SCAN NOW")

            SETTINGS.toggle_lang()
            self.assertEqual(SETTINGS.lang, "ar")
            self.assertTrue(SETTINGS.is_rtl)
            self.assertEqual(t("care_scan_now"), "افحص الآن")
        finally:
            SETTINGS.lang = orig

    def test_format_bytes(self) -> None:
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(1024), "1.0 KB")
        self.assertEqual(format_bytes(5 * 1024 * 1024), "5.0 MB")


if __name__ == "__main__":
    unittest.main()
