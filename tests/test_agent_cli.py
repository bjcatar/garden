from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"
sys.path.insert(0, str(BIN))
import garden_lib as g  # noqa: E402

TODAY = date(2026, 10, 24)


def file(day, slot, repo, path="a.py"):
    return {"type": "file", "day": day, "slot": slot, "repo": repo, "path": path}


def commit(day, slot, repo, digest, subject="edit"):
    return {"type": "git", "day": day, "slot": slot, "repo": repo, "hash": digest, "subject": subject}


def overlap_week():
    events = [
        file("2026-10-24", 28, "garden"),
        file("2026-10-24", 29, "garden"),
        file("2026-10-24", 29, "other"),
        file("2026-10-24", 30, "other"),
    ]
    return g.summarize_activity(events, TODAY)["week"]


def git_only_week():
    events = [commit("2026-10-20", 10, "old", "bbb", "import")]
    return g.summarize_activity(events, TODAY)["week"]


def fresh_stamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat(timespec="seconds")


def stale_stamp() -> str:
    when = datetime.now() - timedelta(seconds=g.HEATMAP_FRESH_SECONDS + 30)
    return when.replace(microsecond=0).isoformat(timespec="seconds")


def load_scan():
    path = BIN / "garden-scan"
    loader = importlib.machinery.SourceFileLoader("garden_scan_agent_cli", str(path))
    spec = importlib.util.spec_from_loader("garden_scan_agent_cli", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["garden_scan_agent_cli"] = mod
    loader.exec_module(mod)
    return mod


class WeekViewTests(unittest.TestCase):
    def test_summary_keeps_machine_hours_and_does_not_add_windows(self):
        week = overlap_week()
        summary = g.week_summary(week)
        self.assertEqual(summary["range"], {"start": "2026-10-19", "end": "2026-10-25"})
        self.assertEqual(summary["daysActive"], 1)
        self.assertEqual(summary["machineSlots"], 3)
        self.assertEqual(summary["machineHours"], 1.5)
        self.assertNotIn("recentCommits", summary)
        self.assertEqual([item["name"] for item in summary["projects"]], ["other", "garden"])
        other = summary["projects"][0]
        self.assertEqual(other["lastTouched"]["label"], "15:00")
        self.assertEqual(other["windows"][0]["label"], "14:30-15:30")
        self.assertEqual(other["windows"][0]["also"], ["garden"])
        window_slots = sum(
            item["endSlot"] - item["startSlot"] + 1
            for project in summary["projects"]
            for item in project["windows"]
        )
        self.assertGreater(window_slots, summary["machineSlots"])
        for project in summary["projects"]:
            self.assertNotIn("hours", project)
            self.assertNotIn("machineHours", project)
            self.assertNotIn("recentCommits", project)

    def test_summary_omits_hours_that_are_not_already_on_the_week(self):
        summary = g.week_summary({
            "start": "2026-10-19",
            "end": "2026-10-25",
            "daysActive": 0,
            "projects": [],
        })
        self.assertNotIn("machineHours", summary)
        self.assertNotIn("machineSlots", summary)
        self.assertEqual(summary["projects"], [])

    def test_summary_includes_commits_already_on_the_week(self):
        summary = g.week_summary(git_only_week())
        self.assertEqual(summary["machineHours"], 0)
        self.assertEqual(summary["recentCommits"][0]["subject"], "import")
        self.assertEqual(summary["recentCommits"][0]["repo"], "old")
        self.assertNotIn("line", summary["recentCommits"][0])

    def test_resume_is_shorter_than_the_week_note(self):
        week = overlap_week()
        note = g.week_markdown(week)
        resume = g.resume_markdown(week)
        self.assertEqual(note, week["markdown"])
        self.assertLess(len(resume), len(note))
        self.assertTrue(resume.startswith("# Resume\n"))
        self.assertIn("1 day active · 1.5h on this machine", resume)
        self.assertIn("other · Last touched 2026-10-24 15:00 · a.py · 1 day active", resume)
        self.assertIn("Sat 14:30-15:30 · also garden", resume)
        self.assertIn("garden · Last touched 2026-10-24 14:30 · a.py · 1 day active", resume)
        self.assertIn("Sat 14:00-15:00 · also other", resume)
        self.assertNotIn("## Days", resume)
        self.assertNotIn("## Windows", resume)
        self.assertNotIn("## Note", resume)
        self.assertNotIn("Project windows overlap", resume)
        self.assertNotIn("2h", resume)

    def test_resume_keeps_commits_and_a_quiet_week_stays_short(self):
        resume = g.resume_markdown(git_only_week())
        self.assertIn("import · old · 05:00", resume)
        self.assertIn("old · Last touched 2026-10-20 05:00", resume)
        self.assertIn("Tue 05:00-05:30 · commit only", resume)
        self.assertNotIn("## Days", resume)
        quiet = g.resume_markdown(g.summarize_activity([], TODAY)["week"])
        self.assertEqual(
            quiet,
            "# Resume\n\n2026-10-19 to 2026-10-25\n\nNo observed time on this machine this week\n",
        )
        self.assertNotIn("## Projects", quiet)

    def test_week_markdown_rejects_a_missing_note(self):
        self.assertEqual(g.week_markdown({}), "")
        self.assertEqual(g.week_markdown({"markdown": "hello"}), "")
        self.assertEqual(g.week_markdown({"markdown": "# This week\n\n"}), "# This week\n\n")

    def test_heatmap_freshness_matches_the_fifteen_minute_timer(self):
        now = datetime(2026, 10, 25, 12, 0, 0)
        self.assertEqual(g.HEATMAP_FRESH_SECONDS, 15 * 60)
        self.assertTrue(g.heatmap_is_fresh({"generatedAt": "2026-10-25T11:45:00"}, now))
        self.assertFalse(g.heatmap_is_fresh({"generatedAt": "2026-10-25T11:44:59"}, now))
        self.assertTrue(g.heatmap_is_fresh({"generatedAt": "2026-10-25T12:00:30"}, now))
        self.assertFalse(g.heatmap_is_fresh({"generatedAt": "2026-10-25T12:02:00"}, now))
        self.assertFalse(g.heatmap_is_fresh({}, now))
        self.assertFalse(g.heatmap_is_fresh({"generatedAt": "not-a-time"}, now))


class AgentCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.scan = load_scan()
        state = root / "garden"
        state.mkdir()
        self.scan.STATE_DIR = state
        self.scan.SETTINGS_PATH = state / "settings.json"
        self.scan.HEATMAP_PATH = state / "heatmap.json"
        self.scan.STATE_PATH = state / "state.json"
        self.scan.LEDGER_PATH = state / "ledger.jsonl"
        self.scan.LOCK_PATH = state / "scan.lock"
        self.scan.USAGE_DIR = root / "usage"
        self.scan.USAGE_DIR.mkdir()
        self.note_path = state / "this-week.md"

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = self.scan.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def write_heatmap(self, week, generated_at):
        text = json.dumps({"generatedAt": generated_at, "activity": {"week": week}}) + "\n"
        self.scan.HEATMAP_PATH.write_text(text, encoding="utf-8")
        return text

    def write_quiet_settings(self):
        self.scan.SETTINGS_PATH.write_text(
            json.dumps({
                "roots": [],
                "authorEmails": ["dev@example.com"],
                "sources": {"files": False, "git": False, "agents": False},
            }) + "\n",
            encoding="utf-8",
        )

    def test_week_md_prints_the_stored_note_without_a_rescan(self):
        week = overlap_week()
        stored = self.write_heatmap(week, fresh_stamp())
        code, out, err = self.run_cli(["--week-md"])
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertEqual(out, week["markdown"])
        self.assertTrue(out.startswith("# This week\n"))
        self.assertEqual(self.scan.HEATMAP_PATH.read_text(encoding="utf-8"), stored)
        self.assertFalse(self.scan.STATE_PATH.exists())
        self.assertFalse(self.note_path.exists())

    def test_week_md_errors_when_the_heatmap_is_missing(self):
        code, out, err = self.run_cli(["--week-md"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Needs a scan", err)
        self.assertFalse(self.scan.HEATMAP_PATH.exists())
        self.assertFalse(self.note_path.exists())

    def test_week_md_errors_when_a_fresh_heatmap_has_no_note(self):
        stored = self.write_heatmap({"start": "2026-10-19"}, fresh_stamp())
        code, out, err = self.run_cli(["--week-md"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Needs a scan", err)
        self.assertEqual(self.scan.HEATMAP_PATH.read_text(encoding="utf-8"), stored)
        self.assertFalse(self.scan.STATE_PATH.exists())

    def test_stale_heatmap_is_scanned_before_week_md(self):
        self.write_quiet_settings()
        self.write_heatmap(overlap_week(), stale_stamp())
        code, out, err = self.run_cli(["--week-md"])
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith("# This week\n"))
        self.assertNotIn("1.5h", out)
        snap = json.loads(self.scan.HEATMAP_PATH.read_text(encoding="utf-8"))
        self.assertEqual(out, snap["activity"]["week"]["markdown"])
        self.assertTrue(self.scan.STATE_PATH.exists())

    def test_scan_flag_rescans_a_fresh_heatmap(self):
        self.write_quiet_settings()
        stored = self.write_heatmap(overlap_week(), fresh_stamp())
        code, out, err = self.run_cli(["--scan", "--week-md"])
        self.assertEqual(code, 0, err)
        self.assertNotEqual(self.scan.HEATMAP_PATH.read_text(encoding="utf-8"), stored)
        self.assertTrue(out.startswith("# This week\n"))
        self.assertTrue(self.scan.STATE_PATH.exists())

    def test_week_json_is_compact_and_skips_a_fresh_rescan(self):
        week = overlap_week()
        stored = self.write_heatmap(week, fresh_stamp())
        code, out, err = self.run_cli(["--week-json"])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.scan.HEATMAP_PATH.read_text(encoding="utf-8"), stored)
        self.assertFalse(self.scan.STATE_PATH.exists())
        self.assertNotIn(", ", out)
        self.assertNotIn(": ", out)
        summary = json.loads(out)
        self.assertEqual(summary["machineHours"], 1.5)
        self.assertEqual(summary["daysActive"], 1)
        self.assertEqual(summary["projects"][0]["name"], "other")
        self.assertEqual(summary["projects"][0]["windows"][0]["label"], "14:30-15:30")
        self.assertNotIn("markdown", summary)
        for project in summary["projects"]:
            self.assertNotIn("machineHours", project)

    def test_resume_md_prints_the_handoff_without_a_rescan(self):
        week = overlap_week()
        stored = self.write_heatmap(week, fresh_stamp())
        code, out, err = self.run_cli(["--resume-md"])
        self.assertEqual(code, 0, err)
        self.assertEqual(out, g.resume_markdown(week))
        self.assertLess(len(out), len(week["markdown"]))
        self.assertEqual(self.scan.HEATMAP_PATH.read_text(encoding="utf-8"), stored)
        self.assertFalse(self.scan.STATE_PATH.exists())

    def test_write_week_overwrites_one_state_file(self):
        week = overlap_week()
        self.write_heatmap(week, fresh_stamp())
        code, out, err = self.run_cli(["--write-week"])
        self.assertEqual(code, 0, err)
        self.assertEqual(out, str(self.note_path) + "\n")
        self.assertEqual(self.note_path.read_text(encoding="utf-8"), week["markdown"])
        again, out2, err2 = self.run_cli(["--write-week"])
        self.assertEqual(again, 0, err2)
        self.assertEqual(out2, str(self.note_path) + "\n")
        self.assertEqual(self.note_path.read_text(encoding="utf-8"), week["markdown"])
        names = sorted(path.name for path in self.scan.STATE_DIR.iterdir())
        self.assertEqual(names, ["heatmap.json", "this-week.md"])

    def test_write_week_does_not_create_a_file_when_the_note_is_missing(self):
        code, out, err = self.run_cli(["--write-week"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Needs a scan", err)
        self.assertFalse(self.note_path.exists())

    def test_help_names_each_week_flag_and_does_not_scan(self):
        code, out, err = self.run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        for flag in ("--week-md", "--week-json", "--resume-md", "--write-week", "--scan"):
            self.assertIn(flag, out)
        self.assertIn("15 minutes", out)
        self.assertIn("do not", out.lower())
        self.assertIn("this-week.md", out)
        self.assertFalse(self.scan.HEATMAP_PATH.exists())
        self.assertFalse(self.scan.STATE_PATH.exists())

    def test_two_week_flags_fail_without_writing(self):
        self.write_heatmap(overlap_week(), fresh_stamp())
        code, out, err = self.run_cli(["--week-md", "--resume-md"])
        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")
        self.assertIn("--week-md", err)
        self.assertFalse(self.note_path.exists())
        self.assertFalse(self.scan.STATE_PATH.exists())

    def test_invalid_heatmap_json_is_scanned(self):
        self.write_quiet_settings()
        self.scan.HEATMAP_PATH.write_text("{", encoding="utf-8")
        code, out, err = self.run_cli(["--week-json"])
        self.assertEqual(code, 0, err)
        summary = json.loads(out)
        self.assertIn("range", summary)
        self.assertIn("machineHours", summary)
        self.assertTrue(self.scan.STATE_PATH.exists())
