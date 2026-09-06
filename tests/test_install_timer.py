"""Tests for garden-scan --install-timer with a fake prefix. No systemd."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"


def load_scan():
    path = BIN / "garden-scan"
    loader = importlib.machinery.SourceFileLoader("garden_scan_timer", str(path))
    spec = importlib.util.spec_from_loader("garden_scan_timer", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


scan = load_scan()


class InstallTimerTests(unittest.TestCase):
    def test_install_copies_units_under_prefix(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "systemd" / "user"
            rc = scan.install_timer(dest, run_systemctl=False)
            self.assertEqual(rc, 0)
            self.assertTrue((dest / "garden-scan.service").is_file())
            self.assertTrue((dest / "garden-scan.timer").is_file())
            text = (dest / "garden-scan.service").read_text(encoding="utf-8")
            self.assertIn("bjcatar.garden", text)

    def test_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "user"
            self.assertEqual(scan.install_timer(dest, run_systemctl=False), 0)
            self.assertEqual(scan.install_timer(dest, run_systemctl=False), 0)
            self.assertEqual(len(list(dest.glob("garden-scan.*"))), 2)

    def test_uninstall_removes_units(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "user"
            scan.install_timer(dest, run_systemctl=False)
            rc = scan.uninstall_timer(dest, run_systemctl=False)
            self.assertEqual(rc, 0)
            self.assertFalse((dest / "garden-scan.service").exists())
            self.assertFalse((dest / "garden-scan.timer").exists())

    def test_uninstall_missing_is_ok(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "user"
            dest.mkdir()
            self.assertEqual(scan.uninstall_timer(dest, run_systemctl=False), 0)


if __name__ == "__main__":
    unittest.main()
