"""Tests for the cross-platform Debian (.deb) package builder and Python syntax validation."""

from __future__ import annotations

from pathlib import Path
import io
import py_compile
import tarfile
import tempfile
import unittest

from scripts.build_deb import build_deb


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestPackagingAndSyntax(unittest.TestCase):
    def test_all_python_sources_compile_cleanly(self) -> None:
        py_files = list((PROJECT_ROOT / "zorincare").rglob("*.py")) + list(
            (PROJECT_ROOT / "scripts").rglob("*.py")
        )
        self.assertGreaterEqual(len(py_files), 14)
        for pf in py_files:
            py_compile.compile(str(pf), doraise=True)

    def test_build_deb_produces_valid_ar_and_lf_tarballs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            deb_file = build_deb(PROJECT_ROOT, Path(tmp))
            self.assertTrue(deb_file.exists())
            raw = deb_file.read_bytes()
            self.assertTrue(raw.startswith(b"!<arch>\n"))

            # Parse `ar` archive members
            offset = 8
            members: dict[str, bytes] = {}
            while offset < len(raw):
                hdr = raw[offset : offset + 60]
                self.assertEqual(len(hdr), 60)
                self.assertEqual(hdr[58:60], b"`\n")
                name = hdr[0:16].decode("ascii").strip()
                size = int(hdr[48:58].decode("ascii").strip())
                payload = raw[offset + 60 : offset + 60 + size]
                members[name] = payload
                offset += 60 + size + (size % 2)

            self.assertEqual(members["debian-binary"], b"2.0\n")
            self.assertIn("control.tar.gz", members)
            self.assertIn("data.tar.gz", members)

            # Inspect data.tar.gz permissions & LF line endings
            with tarfile.open(fileobj=io.BytesIO(members["data.tar.gz"]), mode="r:gz") as dtar:
                names = {m.name: m for m in dtar.getmembers()}
                self.assertIn("./usr/bin/zorincare-pro", names)
                self.assertIn("./usr/lib/zorincare-pro/zorincare-root-helper", names)
                self.assertIn("./usr/share/applications/com.zorincare.pro.desktop", names)
                self.assertIn("./usr/share/polkit-1/actions/com.zorincare.pro.policy", names)

                self.assertEqual(names["./usr/bin/zorincare-pro"].mode, 0o755)
                self.assertEqual(names["./usr/lib/zorincare-pro/zorincare-root-helper"].mode, 0o755)

                # Verify zero CRLF line endings in executables/scripts
                for key in ("./usr/bin/zorincare-pro", "./usr/lib/zorincare-pro/zorincare-root-helper"):
                    extracted = dtar.extractfile(names[key])
                    assert extracted is not None
                    body = extracted.read()
                    self.assertNotIn(b"\r\n", body, f"Found CRLF in {key}")


if __name__ == "__main__":
    unittest.main()
