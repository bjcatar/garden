"""Week and project summaries from ledger events. Stdlib unittest."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"
sys.path.insert(0, str(BIN))
import garden_lib as g  # noqa: E402

TODAY = date(2026, 10, 24)  # Saturday. This week is Mon 19 through Sun 25.

OVERLAP_NOTE = """\
# This week

2026-10-19 to 2026-10-25

1 day active · 1.5h on this machine

Project windows overlap. They are not added into hours on this machine.

## Days

Mon 2026-10-19.
Tue 2026-10-20.
Wed 2026-10-21.
Thu 2026-10-22.
Fri 2026-10-23.
Sat 2026-10-24. 1.5h
Sun 2026-10-25.

## Windows

Sat 14:00-14:30 · garden
Sat 14:30-15:00 · garden, other
Sat 15:00-15:30 · other

## Projects

### other

Last touched 2026-10-24 15:00 · a.py · 1 day active
Sat 14:30-15:30 · also garden

### garden

Last touched 2026-10-24 14:30 · a.py · 1 day active
Sat 14:00-15:00 · also other

## Note

"""

GIT_ONLY_NOTE = """\
# This week

2026-10-19 to 2026-10-25

No observed time on this machine this week

Project windows overlap. They are not added into hours on this machine.

## Days

Mon 2026-10-19.
Tue 2026-10-20.
Wed 2026-10-21.
Thu 2026-10-22.
Fri 2026-10-23.
Sat 2026-10-24.
Sun 2026-10-25.

## Windows

Tue 05:00-05:30 · old · commit only

## Recent commits

import · old · 05:00

## Projects

### old

Last touched 2026-10-20 05:00
Tue 05:00-05:30 · commit only

## Note

"""

AGENT_NOTE = """\
# This week

2026-10-19 to 2026-10-25

1 day active · 0.5h on this machine

Project windows overlap. They are not added into hours on this machine.

## Days

Mon 2026-10-19.
Tue 2026-10-20.
Wed 2026-10-21.
Thu 2026-10-22. 0.5h
Fri 2026-10-23.
Sat 2026-10-24.
Sun 2026-10-25.

## Windows

Thu 04:00-04:30 · agent

## Note

"""

EMPTY_NOTE = """\
# This week

2026-10-19 to 2026-10-25

No observed time on this machine this week

Project windows overlap. They are not added into hours on this machine.

## Days

Mon 2026-10-19.
Tue 2026-10-20.
Wed 2026-10-21.
Thu 2026-10-22.
Fri 2026-10-23.
Sat 2026-10-24.
Sun 2026-10-25.

## Note

"""


def file(day, slot, repo, path="a.py"):
    return {"type": "file", "day": day, "slot": slot, "repo": repo, "path": path}


def commit(day, slot, repo, digest, subject="edit"):
    return {"type": "git", "day": day, "slot": slot, "repo": repo, "hash": digest, "subject": subject}


def spans(projects):
    return sum(item["endSlot"] - item["startSlot"] + 1 for project in projects for item in project["windows"])


class ActivitySummaryTests(unittest.TestCase):
    def test_overlapping_projects_share_one_machine_hour(self):
        events = [
            file("2026-10-24", 28, "garden"),
            file("2026-10-24", 29, "garden"),
            file("2026-10-24", 29, "other"),
            file("2026-10-24", 30, "other"),
        ]
        out = g.summarize_activity(events, TODAY)
        week = out["week"]
        self.assertEqual(week["machineSlots"], 3)
        self.assertEqual(week["machineHours"], 1.5)
        self.assertEqual(week["daysActive"], 1)
        self.assertEqual(
            [(item["startSlot"], item["endSlot"], item["projects"]) for item in week["spans"]],
            [(28, 28, ["garden"]), (29, 29, ["garden", "other"]), (30, 30, ["other"])],
        )
        self.assertEqual(week["projects"][0]["windows"][0]["also"], ["garden"])
        self.assertGreater(spans(week["projects"]), week["machineSlots"])
        for project in week["projects"]:
            self.assertNotIn("hours", project)
            self.assertNotIn("machineHours", project)
        self.assertEqual(week["headline"], "1 day active · 1.5h on this machine")
        self.assertEqual(
            week["overlap"],
            "Project windows overlap. They are not added into hours on this machine.",
        )
        self.assertEqual([day["caption"] for day in week["days"]], ["", "", "", "", "", "1.5", ""])
        self.assertEqual(
            [item["line"] for item in week["spans"]],
            [
                "Sat 14:00-14:30 · garden",
                "Sat 14:30-15:00 · garden, other",
                "Sat 15:00-15:30 · other",
            ],
        )
        self.assertEqual(week["projects"][0]["touched"], "Last touched 2026-10-24 15:00 · a.py · 1 day active")
        self.assertEqual(week["projects"][0]["windows"][0]["line"], "Sat 14:30-15:30 · also garden")
        self.assertEqual(week["projects"][1]["touched"], "Last touched 2026-10-24 14:30 · a.py · 1 day active")
        self.assertEqual(week["projects"][1]["windows"][0]["line"], "Sat 14:00-15:00 · also other")
        self.assertEqual(
            [(item["touched"], [window["line"] for window in item["windows"]]) for item in out["projects"]],
            [(item["touched"], [window["line"] for window in item["windows"]]) for item in week["projects"]],
        )
        note = week["markdown"]
        self.assertEqual(note, OVERLAP_NOTE)
        self.assertEqual(note.count("1.5h"), 2)
        self.assertNotIn("2h", note)
        self.assertNotIn("2.0h", note)
        self.assertIn(week["headline"], note)
        for item in week["spans"]:
            self.assertIn(item["line"], note)
        for project in week["projects"]:
            self.assertIn(project["touched"], note)
            for window in project["windows"]:
                self.assertIn(window["line"], note)

    def test_consecutive_slots_are_one_window_and_a_gap_splits(self):
        events = [
            file("2026-10-24", 28, "garden"),
            file("2026-10-24", 29, "garden", "b.py"),
            file("2026-10-24", 40, "garden"),
            file("2026-10-24", 10, "garden", "a.py"),
            file("2026-10-24", 10, "garden", "c.py"),
        ]
        windows = g.summarize_activity(events, TODAY)["week"]["projects"][0]["windows"]
        self.assertEqual([(item["startSlot"], item["endSlot"]) for item in windows], [(10, 10), (28, 29), (40, 40)])
        self.assertEqual(windows[1]["label"], "14:00-15:00")
        self.assertEqual(g.summarize_activity(events, TODAY)["week"]["machineSlots"], 4)

    def test_git_only_is_a_window_and_not_machine_time(self):
        events = [commit("2026-10-20", 10, "old", "bbb", "import")]
        out = g.summarize_activity(events, TODAY)
        week = out["week"]
        self.assertEqual(week["machineHours"], 0)
        self.assertEqual(week["daysActive"], 0)
        window = week["projects"][0]["windows"][0]
        self.assertEqual(window["sources"], ["git"])
        self.assertEqual(week["recentCommits"][0]["subject"], "import")
        self.assertEqual(week["recentCommits"][0]["repo"], "old")
        self.assertEqual(week["recentCommits"][0]["line"], "import · old · 05:00")
        self.assertNotIn("line", week["projects"][0]["recentCommits"][0])
        self.assertEqual(out["projects"][0]["recentCommits"][0]["line"], "import · old · 05:00")
        self.assertEqual(out["projects"][0]["touched"], "Last touched 2026-10-20 05:00")
        self.assertEqual(window["line"], "Tue 05:00-05:30 · commit only")
        self.assertEqual(out["projects"][0]["windows"][0]["line"], "Tue 05:00-05:30 · commit only")
        self.assertEqual(week["headline"], "No observed time on this machine this week")
        self.assertEqual([day["caption"] for day in week["days"]], ["", "", "", "", "", "", ""])
        note = week["markdown"]
        self.assertEqual(note, GIT_ONLY_NOTE)
        self.assertEqual(note.count("import · old · 05:00"), 1)

    def test_file_and_git_in_one_slot_are_one_observed_window(self):
        events = [
            file("2026-10-24", 20, "garden"),
            commit("2026-10-24", 20, "garden", "aaa", "fix slots"),
        ]
        week = g.summarize_activity(events, TODAY)["week"]
        self.assertEqual(week["machineHours"], 0.5)
        self.assertEqual(week["projects"][0]["windows"][0]["sources"], ["file", "git"])

    def test_agent_time_counts_without_a_project(self):
        events = [{"type": "agent", "day": "2026-10-22", "slot": 8, "agent": "cursor"}]
        out = g.summarize_activity(events, TODAY)
        self.assertEqual(out["week"]["machineSlots"], 1)
        self.assertEqual(out["week"]["daysActive"], 1)
        self.assertEqual(out["projects"], [])
        self.assertEqual(out["week"]["projects"], [])
        self.assertEqual(out["week"]["headline"], "1 day active · 0.5h on this machine")
        self.assertEqual([day["caption"] for day in out["week"]["days"]], ["", "", "", "0.5", "", "", ""])
        self.assertEqual(out["week"]["spans"][0]["line"], "Thu 04:00-04:30 · agent")
        note = out["week"]["markdown"]
        self.assertEqual(note, AGENT_NOTE)
        self.assertNotIn("## Projects", note)
        self.assertNotIn("## Recent commits", note)

    def test_week_is_monday_through_sunday_and_tomorrow_is_future(self):
        events = [
            file("2026-10-18", 4, "garden"),
            file("2026-10-19", 4, "garden"),
        ]
        week = g.summarize_activity(events, TODAY)["week"]
        self.assertEqual(week["start"], "2026-10-19")
        self.assertEqual(week["end"], "2026-10-25")
        self.assertEqual([day["weekday"] for day in week["days"]], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        self.assertEqual(week["days"][0]["observedSlots"], 1)
        self.assertTrue(week["days"][-1]["future"])
        self.assertEqual(week["days"][-1]["observedSlots"], 0)
        self.assertEqual(week["machineSlots"], 1)
        names = [item["name"] for item in week["projects"]]
        self.assertEqual(names, ["garden"])

    def test_last_touched_and_project_order_follow_the_latest_slot(self):
        events = [
            file("2026-10-12", 4, "garden"),
            file("2026-10-24", 28, "garden"),
            file("2026-10-24", 29, "garden"),
            commit("2026-10-23", 20, "garden", "aaa", "fix slots"),
            file("2026-10-24", 30, "other"),
            commit("2026-10-20", 10, "old", "bbb", "import"),
        ]
        out = g.summarize_activity(events, TODAY)
        self.assertEqual([item["name"] for item in out["week"]["projects"]], ["other", "garden", "old"])
        garden = next(item for item in out["projects"] if item["name"] == "garden")
        self.assertEqual(
            garden["lastTouched"],
            {"day": "2026-10-24", "slot": 29, "label": "14:30", "path": "a.py"},
        )
        self.assertEqual(garden["daysActive"], 2)
        week_garden = next(item for item in out["week"]["projects"] if item["name"] == "garden")
        self.assertEqual(week_garden["daysActive"], 1)
        self.assertTrue(garden["thisWeek"])
        self.assertEqual([item["hash"] for item in out["week"]["recentCommits"]], ["aaa", "bbb"])

    def test_recent_commits_keep_the_newest_of_a_hash_and_cap_at_eight(self):
        events = [commit("2026-10-24", slot, "garden", f"h{slot}") for slot in range(10)]
        events.append(commit("2026-10-24", 1, "garden", "h9", "older copy"))
        week = g.summarize_activity(events, TODAY)["week"]
        commits = week["recentCommits"]
        self.assertEqual(len(commits), 8)
        self.assertEqual(commits[0]["slot"], 9)
        self.assertEqual(commits[0]["subject"], "edit")
        self.assertNotIn("older copy", [item["subject"] for item in commits])
        note = week["markdown"]
        self.assertNotIn("older copy", note)
        marker = "## Recent commits\n\n"
        block = note[note.index(marker) + len(marker):]
        block = block[:block.index("\n\n")]
        self.assertEqual(len(block.split("\n")), 8)

    def test_year_project_keeps_the_latest_windows_only(self):
        events = [file("2026-10-24", slot, "garden") for slot in range(0, 20, 2)]
        out = g.summarize_activity(events, TODAY)
        windows = out["projects"][0]["windows"]
        self.assertEqual(len(windows), 8)
        self.assertEqual(windows[-1]["startSlot"], 18)
        self.assertEqual(len(out["week"]["projects"][0]["windows"]), 10)
        note = out["week"]["markdown"]
        self.assertIn("Sat 00:00-00:30", note)
        self.assertIn("Sat 01:00-01:30", note)
        self.assertNotIn(0, [item["startSlot"] for item in windows])
        self.assertNotIn(2, [item["startSlot"] for item in windows])
        self.assertEqual(out["week"]["headline"], "1 day active · 5h on this machine")
        self.assertNotIn("5.0", note)

    def test_coverage_is_copied_and_not_invented(self):
        out = g.summarize_activity([], TODAY, {"2026-10-19": "unknown", "2026-10-20": "observed"})
        days = {day["date"]: day for day in out["week"]["days"]}
        self.assertEqual(days["2026-10-19"]["coverage"], "unknown")
        self.assertEqual(days["2026-10-20"]["coverage"], "observed")
        self.assertNotIn("coverage", days["2026-10-21"])
        self.assertNotIn("coverage", days["2026-10-25"])
        bare = g.summarize_activity([], TODAY)["week"]["days"][0]
        self.assertNotIn("coverage", bare)

    def test_unknown_days_drop_events(self):
        events = [
            file("2026-10-19", 4, "garden", "Panel.qml"),
            file("2026-10-20", 4, "garden", "src/Heatmap.js"),
        ]
        week = g.summarize_activity(events, TODAY, {"2026-10-19": "unknown", "2026-10-20": "observed"})["week"]
        self.assertEqual(week["machineSlots"], 1)
        self.assertEqual(week["spans"][0]["projects"], ["garden"])
        self.assertEqual(week["projects"][0]["lastTouched"]["path"], "Heatmap.js")
        self.assertEqual(week["days"][0]["coverage"], "unknown")
        self.assertEqual(week["days"][0]["observedSlots"], 0)

    def test_bad_rows_are_ignored(self):
        events = [
            None,
            "nope",
            {"type": "file", "day": "2026-10-24", "slot": True, "repo": "garden"},
            {"type": "file", "day": "2026-10-24", "slot": 99, "repo": "garden"},
            {"type": "noise", "day": "2026-10-24", "slot": 3, "repo": "garden"},
            {"type": "file", "day": "not-a-day", "slot": 3, "repo": "garden"},
            {"type": "file", "day": "2026-10-24", "slot": 3, "path": "a.py"},
            {"type": "file", "day": "2026-10-26", "slot": 3, "repo": "future"},
        ]
        week = g.summarize_activity(events, TODAY)["week"]
        self.assertEqual(week["machineSlots"], 1)
        self.assertEqual(week["projects"], [])
        self.assertEqual(g.summarize_activity(None, TODAY)["week"]["daysActive"], 0)

    def test_empty_ledger_is_a_quiet_week(self):
        out = g.summarize_activity([], TODAY)
        self.assertEqual(out["week"]["daysActive"], 0)
        self.assertEqual(out["week"]["machineHours"], 0)
        self.assertEqual(out["projects"], [])
        self.assertEqual(len(out["week"]["days"]), 7)
        self.assertEqual([day["caption"] for day in out["week"]["days"]], ["", "", "", "", "", "", ""])
        self.assertEqual(out["week"]["markdown"], EMPTY_NOTE)

    def test_square_captions_skip_coverage_that_is_not_observed_time(self):
        events = [
            file("2026-10-19", 4, "garden"),
            file("2026-10-20", 4, "garden"),
            file("2026-10-21", 4, "garden"),
            file("2026-10-22", 4, "garden"),
            file("2026-10-24", 4, "garden"),
            file("2026-10-24", 5, "garden"),
        ]
        coverage = {
            "2026-10-19": "unknown",
            "2026-10-20": "gap",
            "2026-10-21": "sampled",
            "2026-10-22": "git-history-only",
            "2026-10-23": "observed",
            "2026-10-24": "empty",
        }
        week = g.summarize_activity(events, TODAY, coverage)["week"]
        self.assertEqual(
            [day["caption"] for day in week["days"]],
            ["", "", "0.5", "", "", "1", ""],
        )
        self.assertEqual(week["days"][2]["observedSlots"], 1)
        self.assertEqual(week["days"][3]["observedSlots"], 1)
        self.assertEqual(week["headline"], "4 days active · 2.5h on this machine")
        self.assertNotIn("1.0", week["markdown"])
        self.assertNotIn("2.0", week["markdown"])
        self.assertIn("Tue 2026-10-20.\n", week["markdown"])
        self.assertIn("Wed 2026-10-21. 0.5h\n", week["markdown"])
        self.assertIn("Thu 2026-10-22.\n", week["markdown"])
        self.assertIn("Sat 2026-10-24. 1h\n", week["markdown"])
        self.assertIn(week["headline"], week["markdown"])

    def test_a_dashed_subject_stays_under_the_week_heading(self):
        events = [commit("2026-10-24", 10, "garden", "abc", "- drop the flag")]
        note = g.summarize_activity(events, TODAY)["week"]["markdown"]
        self.assertTrue(note.startswith("# This week\n"))
        self.assertIn("- drop the flag · garden · 05:00", note)

    def test_the_same_events_repeat_the_same_note(self):
        events = [file("2026-10-24", 28, "garden"), file("2026-10-24", 30, "other")]
        first = g.summarize_activity(events, TODAY)["week"]["markdown"]
        second = g.summarize_activity(events, TODAY)["week"]["markdown"]
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("# This week\n"))
        self.assertTrue(first.endswith("## Note\n\n"))


def load_scan():
    path = BIN / "garden-scan"
    loader = importlib.machinery.SourceFileLoader("garden_scan_activity", str(path))
    spec = importlib.util.spec_from_loader("garden_scan_activity", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class HeatmapActivityTests(unittest.TestCase):
    def test_heatmap_includes_the_week_summary(self):
        scan = load_scan()
        today = date.today().isoformat()
        with tempfile.TemporaryDirectory() as raw:
            ledger = Path(raw) / "ledger.jsonl"
            ledger.write_text(json.dumps(file(today, 10, "garden")) + "\n", encoding="utf-8")
            scan.LEDGER_PATH = ledger
            scan.timer_enabled = lambda: False
            snap = scan.build_heatmap(
                {"roots": [], "excludeRepos": [], "sources": {}, "slotMinutes": 30},
                {},
                [],
            )
        self.assertEqual(snap["activity"]["week"]["machineSlots"], 1)
        self.assertEqual(snap["activity"]["week"]["machineHours"], 0.5)
        self.assertNotIn("hours", snap["activity"]["projects"][0])
        self.assertEqual(snap["days"][today]["observedSlots"], 1)
        self.assertTrue(snap["days"][today]["coverage"])
        note = snap["activity"]["week"]["markdown"]
        self.assertTrue(note.startswith("# This week\n"))
        self.assertTrue(note.endswith("## Note\n\n"))
        self.assertIn(snap["activity"]["week"]["headline"], note)


if __name__ == "__main__":
    unittest.main()
