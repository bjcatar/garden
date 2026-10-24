from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import garden_lib as g  # noqa: E402


class CoverageTests(unittest.TestCase):
    def test_usage(self):
        monday_6pm = datetime(2026, 10, 19, 18, 0).timestamp()
        tuesday_3pm = datetime(2026, 10, 20, 15, 0).timestamp()
        wednesday_9am = datetime(2026, 10, 21, 9, 0).timestamp()
        start = date(2026, 10, 18)
        end = date(2026, 10, 21)

        assert g.process_failed(0, None) is False
        assert g.process_failed(1, None) is True
        assert g.process_failed(None, "timeout") is True
        assert g.process_failed(None, "missing") is True

        monday = g.plan_scan(
            g.parse_scan_state(None),
            [],
            g.ProbeOk(events=()),
            g.ProbeOk(events=()),
            g.ProbeOff(),
            monday_6pm,
            datetime(2026, 10, 19, 0, 0).timestamp(),
        )
        assert monday.state.first_sample_at == monday_6pm
        assert monday.state.file_cursor == monday_6pm
        assert monday.state.file_windows == (
            g.FileWindow(datetime(2026, 10, 19, 0, 0).timestamp(), monday_6pm),
        )
        assert g.scan_status_text(monday.state, True) == (
            "Last scan Monday, Oct 19, 2026, 6:00 PM. Timer enabled."
        )

        failed = g.plan_scan(
            monday.state,
            [],
            g.ProbeFailed(events=()),
            g.ProbeFailed(events=()),
            g.ProbeOff(),
            tuesday_3pm,
            datetime(2026, 10, 20, 0, 0).timestamp(),
        )
        assert failed.state.file_cursor == monday_6pm
        assert failed.state.file_windows == monday.state.file_windows
        assert failed.state.files_ok_at == monday_6pm
        assert g.scan_status_text(failed.state, True) == (
            "Last scan failed Tuesday, Oct 20, 2026, 3:00 PM. "
            "Files last ok Monday, Oct 19, 2026, 6:00 PM. "
            "Git last ok Monday, Oct 19, 2026, 6:00 PM. Timer enabled."
        )

        wednesday = g.plan_scan(
            failed.state,
            [],
            g.ProbeOk(events=()),
            g.ProbeOk(events=()),
            g.ProbeOff(),
            wednesday_9am,
            datetime(2026, 10, 21, 0, 0).timestamp(),
        )
        assert wednesday.state.file_windows == (
            g.FileWindow(datetime(2026, 10, 19, 0, 0).timestamp(), wednesday_9am),
        )
        stored = g.parse_scan_state(wednesday.state.to_json())
        assert stored.file_windows == wednesday.state.file_windows
        assert "lastSampleAt" not in wednesday.state.to_json()

        retry = g.plan_scan(
            wednesday.state,
            list(wednesday.events_to_append),
            g.ProbeOk(events=wednesday.events_to_append),
            g.ProbeOk(events=()),
            g.ProbeOff(),
            wednesday_9am,
            datetime(2026, 10, 21, 0, 0).timestamp(),
        )
        assert retry.events_to_append == ()
        assert retry.state.file_windows == wednesday.state.file_windows

        ev = {"type": "file", "day": "2026-10-20", "slot": 36, "repo": "~/Projects/app", "path": "a.py"}
        first = g.plan_scan(
            g.parse_scan_state(None),
            [],
            g.ProbeOk(events=(ev,)),
            g.ProbeOff(),
            g.ProbeOff(),
            wednesday_9am,
            datetime(2026, 10, 21, 0, 0).timestamp(),
        )
        assert len(first.events_to_append) == 1
        replay = g.plan_scan(
            g.parse_scan_state(None),
            list(first.events_to_append),
            g.ProbeOk(events=(ev,)),
            g.ProbeOff(),
            g.ProbeOff(),
            wednesday_9am,
            datetime(2026, 10, 21, 0, 0).timestamp(),
        )
        assert replay.events_to_append == ()
        assert replay.state.file_windows == first.state.file_windows

        days = g.cover_days([], wednesday.state, start, end)
        tuesday = days["2026-10-20"]
        sunday = days["2026-10-18"]
        assert sunday.coverage == "unknown"
        assert sunday.paint == "dim"
        assert sunday.label == "Sunday, Oct 18, 2026 · not monitored yet"
        assert tuesday.coverage == "sampled"
        assert tuesday.observed_slots == 0
        assert tuesday.paint == "dim"
        assert tuesday.intervals == (
            (datetime(2026, 10, 20, 0, 0).timestamp(), datetime(2026, 10, 21, 0, 0).timestamp()),
        )
        assert tuesday.read_at == wednesday_9am
        assert tuesday.label == (
            "Tuesday, Oct 20, 2026 · no file changes still on disk · "
            "sampled Wednesday, Oct 21, 2026, 9:00 AM"
        )
        assert days["2026-10-21"].label == (
            "Wednesday, Oct 21, 2026 · no file changes in the sampled window · "
            "12:00 AM to 9:00 AM"
        )
        assert days["2026-10-21"].headline == "No file changes in the sampled window today"
        assert "built" not in days["2026-10-21"].headline
        assert "waiting" not in days["2026-10-21"].headline
        assert "observed" not in tuesday.label
        assert "0h" not in tuesday.label
        row = tuesday.as_heatmap_day()
        assert row["coverage"] == "sampled"
        assert row["observedSlots"] == 0
        assert row["paint"] == "dim"
        assert row["label"] == tuesday.label
        assert "intervals" not in row
        assert row["coverage"] != "observed"

        legacy = g.parse_scan_state({
            "firstSampleAt": monday_6pm,
            "lastSampleAt": tuesday_3pm,
        })
        assert legacy.file_cursor == tuesday_3pm
        assert legacy.file_windows == ()
        assert legacy.files_ok_at is None
        gap = g.cover_days([], legacy, start, end)["2026-10-20"]
        assert gap.coverage == "gap"
        assert gap.paint == "dim"
        assert gap.label == "Tuesday, Oct 20, 2026 · no successful scan"
        assert g.cover_days([], legacy, start, date(2026, 10, 20))["2026-10-20"].headline == (
            "No successful scan today"
        )
        assert g.cover_days([], legacy, start, date(2026, 10, 18))["2026-10-18"].headline == (
            "Not monitored yet"
        )

        caught_up = g.plan_scan(
            legacy, [], g.ProbeOk(events=()), g.ProbeOk(events=()), g.ProbeOff(),
            wednesday_9am, datetime(2026, 10, 21, 0, 0).timestamp(),
        )
        late = g.cover_days([], caught_up.state, start, end)["2026-10-20"]
        assert late.coverage == "sampled"
        assert late.intervals == (
            (tuesday_3pm, datetime(2026, 10, 21, 0, 0).timestamp()),
        )
        assert late.label == (
            "Tuesday, Oct 20, 2026 · no file changes in the sampled window · "
            "3:00 PM to midnight · before 3:00 PM was not sampled · "
            "read Wednesday, Oct 21, 2026, 9:00 AM"
        )
        assert g.cover_days([], caught_up.state, start, end)["2026-10-19"].coverage == "gap"

        lit = g.cover_days(
            [{"type": "file", "day": "2026-10-19", "slot": 36, "repo": "~/Projects/garden", "path": "a.py"}],
            legacy, start, date(2026, 10, 19),
        )
        assert lit["2026-10-19"].coverage == "sampled"
        assert lit["2026-10-19"].paint == "lit"
        assert lit["2026-10-19"].observed_slots == 1
        assert lit["2026-10-19"].label == "Monday, Oct 19, 2026 · 1 half-hour sampled"
        assert lit["2026-10-19"].headline == "1 half-hour sampled on this machine today"
        two_slots = g.cover_days(
            [
                {"type": "file", "day": "2026-10-19", "slot": 36, "repo": "~/Projects/garden", "path": "a.py"},
                {"type": "file", "day": "2026-10-19", "slot": 37, "repo": "~/Projects/garden", "path": "b.py"},
            ],
            legacy, start, date(2026, 10, 19),
        )
        assert two_slots["2026-10-19"].headline == "2 half-hours sampled on this machine today"
        assert two_slots["2026-10-19"].label == "Monday, Oct 19, 2026 · 2 half-hours sampled"
        read_later = g.cover_days(
            [{"type": "file", "day": "2026-10-19", "slot": 36, "repo": "~/Projects/garden", "path": "a.py"}],
            wednesday.state, start, end,
        )
        assert read_later["2026-10-19"].label == (
            "Monday, Oct 19, 2026 · 1 half-hour sampled · "
            "read Wednesday, Oct 21, 2026, 9:00 AM"
        )

        git_only = g.cover_days(
            [{"type": "git", "day": "2026-10-20", "slot": 36, "hash": "abc", "repo": "~/Projects/garden"}],
            wednesday.state, start, end,
        )
        assert git_only["2026-10-20"].coverage == "git-history-only"
        assert git_only["2026-10-20"].paint == "pale"
        assert git_only["2026-10-20"].observed_slots == 0
        assert git_only["2026-10-20"].label == (
            "Tuesday, Oct 20, 2026 · git history only, may not have happened on this PC"
        )
        assert g.cover_days(
            [{"type": "git", "day": "2026-10-20", "slot": 36, "hash": "abc", "repo": "~/Projects/garden"}],
            legacy, start, date(2026, 10, 20),
        )["2026-10-20"].headline == "Git history only today"
        holed = g.parse_scan_state({
            "firstSampleAt": datetime(2026, 10, 20, 0, 0).timestamp(),
            "fileCursor": datetime(2026, 10, 21, 0, 0).timestamp(),
            "fileWindows": [
                [datetime(2026, 10, 20, 0, 0).timestamp(), datetime(2026, 10, 20, 10, 0).timestamp()],
                [datetime(2026, 10, 20, 18, 0).timestamp(), datetime(2026, 10, 21, 0, 0).timestamp()],
            ],
        })
        assert g.cover_days([], holed, start, end)["2026-10-20"].label == (
            "Tuesday, Oct 20, 2026 · no file changes in the sampled windows · "
            "12:00 AM to 10:00 AM, 6:00 PM to midnight"
        )

        partial = g.plan_scan(
            monday.state, [], g.ProbeOk(events=()), g.ProbeFailed(events=()), g.ProbeOff(),
            wednesday_9am, datetime(2026, 10, 21, 0, 0).timestamp(),
        )
        assert partial.state.file_cursor == wednesday_9am
        assert g.scan_status_text(partial.state, True) == (
            "Last scan Wednesday, Oct 21, 2026, 9:00 AM, partial, files ok, git failed. "
            "Git last ok Monday, Oct 19, 2026, 6:00 PM. Timer enabled."
        )
        assert g.scan_status_text(g.parse_scan_state(None), False) == "No successful scan yet. Timer off."
        fresh_fail = g.plan_scan(
            g.parse_scan_state(None), [],
            g.ProbeFailed(events=()), g.ProbeOff(), g.ProbeOff(),
            tuesday_3pm, datetime(2026, 10, 20, 0, 0).timestamp(),
        )
        assert fresh_fail.state.first_sample_at is None
        assert fresh_fail.state.file_cursor == 0
        assert g.scan_status_text(fresh_fail.state, True) == (
            "Last scan failed Tuesday, Oct 20, 2026, 3:00 PM. "
            "No successful file scan yet. Timer enabled."
        )
        assert g.week_clause(0) == "No half-hours sampled this week on this Omarchy box"
        assert g.week_clause(1) == "1 half-hour sampled this week on this Omarchy box"
        assert g.week_clause(8) == "8 half-hours sampled this week on this Omarchy box"


if __name__ == "__main__":
    unittest.main()
