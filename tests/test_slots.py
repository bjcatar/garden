"""Tests for Garden slot math and settings. Stdlib unittest (no pytest)."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import garden_lib as g  # noqa: E402


class SlotMathTests(unittest.TestCase):
    def test_two_events_same_half_hour_are_one_slot(self):
        day = "2026-09-05"
        a = g.event_slot(day, hour=14, minute=5)
        b = g.event_slot(day, hour=14, minute=20)
        self.assertEqual(a, b)
        self.assertEqual(g.union_slots([a, b]), {a})

    def test_events_in_adjacent_half_hours_are_two_slots(self):
        day = "2026-09-05"
        a = g.event_slot(day, hour=14, minute=5)
        b = g.event_slot(day, hour=14, minute=35)
        self.assertEqual(len(g.union_slots([a, b])), 2)

    def test_commit_and_file_same_window_count_once(self):
        slots = g.union_slots([
            g.event_slot("2026-09-05", 10, 0, source="git"),
            g.event_slot("2026-09-05", 10, 10, source="file"),
        ])
        self.assertEqual(len(slots), 1)

    def test_vault_backup_subject_is_ignored(self):
        self.assertTrue(g.ignore_subject("vault backup: 2026-09-04 23:57:18"))
        self.assertFalse(g.ignore_subject("fix heatmap width"))

    def test_level_cuts_are_fixed_not_relative(self):
        self.assertEqual(g.day_level(0), 0)
        self.assertEqual(g.day_level(1), 1)
        self.assertEqual(g.day_level(2), 2)
        self.assertEqual(g.day_level(3), 2)
        self.assertEqual(g.day_level(4), 3)
        self.assertEqual(g.day_level(7), 3)
        self.assertEqual(g.day_level(8), 4)
        self.assertEqual(g.day_level(20), 4)

    def test_slot_minutes_stay_thirty(self):
        s = g.normalize_settings({"slotMinutes": 15})
        self.assertEqual(s["slotMinutes"], 30)

    def test_hours_active_from_slots(self):
        self.assertEqual(g.hours_active(6), 3.0)
        self.assertEqual(g.hours_active(1), 0.5)

    def test_file_since_keeps_last_sample_across_midnight(self):
        last = 1_700_000_000.0
        midnight = last + 4000
        self.assertEqual(g.file_since_ts(last, midnight), last)
        self.assertEqual(g.file_since_ts(0, midnight), midnight)


class SettingsTests(unittest.TestCase):
    def test_empty_roots_do_not_fall_back_to_documents(self):
        s = g.normalize_settings({"roots": []})
        self.assertEqual(s["roots"], [])

    def test_home_root_is_rejected(self):
        self.assertFalse(g.validate_root(str(Path.home())))
        self.assertFalse(g.validate_root("~"))

    def test_projects_is_accepted_when_it_exists(self):
        projects = Path.home() / "Projects"
        if projects.is_dir():
            self.assertTrue(g.validate_root(str(projects)))

    def test_missing_author_emails_do_not_count_everyone(self):
        s = g.normalize_settings({"authorEmails": []})
        self.assertEqual(s["authorEmails"], [])
        self.assertFalse(g.git_signal_enabled(s))


class GitFilterTests(unittest.TestCase):
    def test_email_match_is_exact_and_casefold(self):
        self.assertTrue(g.author_ok("me@x.com", ["me@x.com"]))
        self.assertTrue(g.author_ok("ME@X.COM", ["me@x.com"]))
        self.assertFalse(g.author_ok("other@x.com", ["me@x.com"]))
        self.assertFalse(g.author_ok("me@x.com", []))


if __name__ == "__main__":
    unittest.main()
