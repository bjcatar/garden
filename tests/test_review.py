"""Month-in-review: encouragement without streak guilt. Stdlib unittest."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import garden_lib as g  # noqa: E402


def lit(iso: str, *slots: int):
    return {"day": iso, "slots": set(slots)}


class ReviewGateTests(unittest.TestCase):
    def test_six_active_days_is_silent(self):
        days = [lit(f"2026-08-0{i}", 20) for i in range(1, 7)]
        self.assertIsNone(g.collect_review(days, today=date(2026, 8, 10)))

    def test_seven_active_days_returns_payload(self):
        days = [lit(f"2026-08-0{i}", 20) for i in range(1, 8)]
        out = g.collect_review(days, today=date(2026, 8, 10))
        self.assertIsNotNone(out)
        self.assertIn("sentence", out)
        self.assertTrue(out["sentence"])


class ReviewContentTests(unittest.TestCase):
    def test_sunday_belongs_to_previous_week(self):
        # Monday 10 Aug 2026. Sunday 9 Aug is last week.
        days = [
            lit("2026-08-03", 10),  # last week Mon
            lit("2026-08-04", 10),
            lit("2026-08-05", 10),
            lit("2026-08-06", 10),
            lit("2026-08-07", 10),
            lit("2026-08-08", 10),
            lit("2026-08-09", 10, 11),  # Sunday last week: 1h
            lit("2026-08-10", 42),  # this week Monday: 0.5h at 21:00
        ]
        out = g.collect_review(days, today=date(2026, 8, 10))
        self.assertEqual(out["hoursThisWeek"], 0.5)
        self.assertEqual(out["hoursLastWeek"], 4.0)  # 6 days * 0.5 + 1.0 Sunday

    def test_peak_weekday_and_hour(self):
        days = [
            lit("2026-08-06", 42),  # Thu 21:00
            lit("2026-08-13", 42),
            lit("2026-08-20", 42),
            lit("2026-08-07", 10),  # Fri morning once
            lit("2026-08-08", 10),
            lit("2026-08-09", 10),
            lit("2026-08-10", 10),
        ]
        out = g.collect_review(days, today=date(2026, 8, 20))
        self.assertEqual(out["peakWeekday"], "Thursday")
        self.assertIn("Thursday", out["sentence"])
        self.assertIn("05:00", out["sentence"])


if __name__ == "__main__":
    unittest.main()
