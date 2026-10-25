from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import garden_lib as g  # noqa: E402

NOTE = "Build and dependency folders are skipped by the scanner. They are not mutes."


class SettingsSheetTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.projects = self.home / "Projects"
        self.projects.mkdir()
        (self.home / "plain").mkdir()
        (self.home / "zeta").mkdir()
        (self.home / ".secret").mkdir()
        (self.home / "notes.txt").write_text("x\n", encoding="utf-8")
        for index in range(9):
            (self.home / f"b{index}").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_home_spellings_do_not_add_a_root(self):
        base = {"roots": ["keep"], "authorEmails": ["a@b.c"]}
        for raw in ("$HOME", "${HOME}", "~", ".", "$HOME/", "~/"):
            decision = g.root_decision(raw, home=self.home)
            self.assertEqual(decision.kind, "home", raw)
            self.assertEqual(decision.token, "home", raw)
            self.assertEqual(decision.stored, "")
            self.assertEqual(decision.display, "")
            self.assertFalse(decision.ok)
            updated = g.apply_add_root(base, raw, home=self.home)
            self.assertEqual(updated["roots"], ["keep"], raw)
            self.assertEqual(base["roots"], ["keep"])
        self.assertFalse(g.validate_root("$HOME"))
        self.assertFalse(g.validate_root("${HOME}"))

    def test_projects_spellings_accept_and_bad_paths_reject(self):
        expected = str(self.projects.resolve())
        for raw in ("$HOME/Projects", "${HOME}/Projects", "~/Projects", "Projects", "$HOME//Projects"):
            decision = g.root_decision(raw, home=self.home)
            self.assertEqual(decision.kind, "accept", raw)
            self.assertTrue(decision.ok, raw)
            self.assertEqual(decision.stored, expected, raw)
            self.assertEqual(decision.display, "~/Projects", raw)
            self.assertEqual(decision.token, "", raw)
            self.assertEqual(decision.offers, ())
        self.assertEqual(g.root_decision("/tmp", home=self.home).token, "outside-home")
        self.assertEqual(g.root_decision(str(self.home / "notes.txt"), home=self.home).token, "not-directory")
        self.assertEqual(g.root_decision(str(self.home / "missing-folder"), home=self.home).token, "missing")
        self.assertEqual(g.root_decision("", home=self.home).token, "empty")
        self.assertEqual(g.root_decision("   ", home=self.home).token, "empty")
        shell = Path("/bin/sh")
        if shell.is_file():
            self.assertEqual(g.root_decision(str(shell), home=self.home).token, "not-directory")

    def test_offers_pin_projects_and_keep_a_plain_directory(self):
        decision = g.root_decision("~", home=self.home)
        names = [Path(stored).name for stored, _display in decision.offers]
        expected = ["Projects", "b0", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "plain", "zeta"]
        self.assertEqual(names, expected)
        self.assertNotIn(".secret", names)
        self.assertNotIn("notes.txt", names)
        self.assertIn("plain", names)
        sheet = g.settings_sheet(
            {"roots": [], "excludeRepos": []},
            [],
            {"version": "0.3.0"},
            home=self.home,
        )
        self.assertEqual([Path(row["stored"]).name for row in sheet["offers"]], expected)
        watched = g.settings_sheet(
            {"roots": [str(self.projects)], "excludeRepos": []},
            [],
            {"version": "0.3.0"},
            home=self.home,
        )
        self.assertEqual(watched["offers"], [])
        forced = g.settings_sheet(
            {"roots": [str(self.projects)], "excludeRepos": []},
            [],
            {"version": "0.3.0"},
            home=self.home,
            force_offers=True,
        )
        self.assertEqual([Path(row["stored"]).name for row in forced["offers"]], expected)

    def test_mute_row_is_the_stored_string_not_a_scanner_skip(self):
        repos = [
            {"path": str(self.projects / "demo"), "name": "demo", "label": "~/Projects/demo"},
            {"path": str(self.projects / "dist"), "name": "dist", "label": "~/Projects/dist"},
            {"path": str(self.home / "node_modules"), "name": "node_modules", "label": "~/node_modules"},
            {"path": str(self.projects / "bare"), "name": "bare", "label": ""},
        ]
        sheet = g.settings_sheet(
            {"roots": ["~/Projects"], "excludeRepos": ["dist"], "ignoreSubject": g.DEFAULT_IGNORE_SUBJECT},
            repos,
            {"version": "0.3.0"},
            home=self.home,
        )
        self.assertEqual([row["stored"] for row in sheet["mutes"]], ["dist"])
        self.assertEqual(sheet["mutes"][0]["hits"], ["~/Projects/dist"])
        self.assertNotIn("node_modules", [row["stored"] for row in sheet["mutes"]])
        self.assertEqual(
            sheet["openRepos"],
            ["~/Projects/demo", "~/node_modules", str(self.projects / "bare")],
        )
        self.assertEqual(sheet["roots"][0]["stored"], "~/Projects")
        self.assertEqual(sheet["roots"][0]["display"], "~/Projects")
        self.assertTrue(sheet["roots"][0]["ok"])
        self.assertNotIn("scanStatus", sheet)
        self.assertEqual(sheet["hardSkipNote"], NOTE)
        self.assertEqual(
            set(sheet),
            {"version", "roots", "offers", "mutes", "openRepos", "subject", "hardSkipNote"},
        )

    def test_add_keeps_the_first_spelling_and_remove_clears_either(self):
        added = g.apply_add_root({"roots": []}, "~/Projects", home=self.home)
        absolute = str(self.projects.resolve())
        again = g.apply_add_root(added, absolute, home=self.home)
        self.assertEqual(len(again["roots"]), 1)
        self.assertEqual(again["roots"], added["roots"])
        self.assertEqual(again["roots"][0], absolute)
        self.assertEqual(g.apply_remove_root(again, "~/Projects", home=self.home)["roots"], [])
        self.assertEqual(g.apply_remove_root(again, absolute, home=self.home)["roots"], [])
        cleared = g.apply_remove_root(again, "~/Projects", home=self.home)
        self.assertEqual(g.apply_remove_root(cleared, absolute, home=self.home)["roots"], [])
        seed = {"roots": ["~/Projects"]}
        kept = g.apply_add_root(seed, absolute, home=self.home)
        self.assertEqual(kept["roots"], ["~/Projects"])
        self.assertEqual(seed["roots"], ["~/Projects"])
        self.assertEqual(g.apply_remove_root(kept, absolute, home=self.home)["roots"], [])
        self.assertEqual(g.apply_remove_root(kept, "~/Projects", home=self.home)["roots"], [])

    def test_mute_stores_a_label_once_and_unmute_needs_that_string(self):
        label = "~/Projects/demo"
        once = g.apply_mute({"excludeRepos": []}, label, True)
        twice = g.apply_mute(once, label, True)
        self.assertEqual(twice["excludeRepos"], [label])
        self.assertEqual(once["excludeRepos"], [label])
        blank = g.apply_mute(twice, "", True)
        spaces = g.apply_mute(twice, "   ", True)
        self.assertEqual(blank["excludeRepos"], [label])
        self.assertEqual(spaces["excludeRepos"], [label])
        self.assertEqual(g.apply_mute({"excludeRepos": ["garden"]}, label, False)["excludeRepos"], ["garden"])
        self.assertEqual(g.apply_mute({"excludeRepos": ["garden"]}, "garden", False)["excludeRepos"], [])
        self.assertEqual(g.apply_mute({"excludeRepos": ["garden"]}, "missing", False)["excludeRepos"], ["garden"])

    def test_manifest_version_and_subject(self):
        self.assertEqual(g.manifest_version({"version": "0.3.0"}), "0.3.0")
        self.assertEqual(g.manifest_version({"version": "v0.3.0"}), "")
        self.assertEqual(g.manifest_version({"version": "0.3"}), "")
        self.assertEqual(g.manifest_version(None), "")
        kept = g.settings_sheet({"roots": [], "ignoreSubject": ""}, [], {"version": "0.3.0"}, home=self.home)
        self.assertEqual(kept["version"], "0.3.0")
        self.assertEqual(kept["subject"]["pattern"], g.DEFAULT_IGNORE_SUBJECT)
        self.assertTrue(kept["subject"]["isDefault"])
        custom = g.settings_sheet(
            {"roots": [], "ignoreSubject": "^wip"},
            [],
            {"version": "v0.3.0"},
            home=self.home,
        )
        self.assertEqual(custom["version"], "")
        self.assertEqual(custom["subject"], {"pattern": "^wip", "isDefault": False})
        self.assertEqual(custom["hardSkipNote"], NOTE)
        self.assertNotIn("scanStatus", custom)


if __name__ == "__main__":
    unittest.main()
