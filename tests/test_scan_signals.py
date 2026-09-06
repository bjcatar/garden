"""Scanner signal tests. Temp dirs only — never ~/Projects. Stdlib unittest."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"
import sys

sys.path.insert(0, str(BIN))
import garden_lib as g  # noqa: E402


def load_scan():
    path = BIN / "garden-scan"
    loader = importlib.machinery.SourceFileLoader("garden_scan", str(path))
    spec = importlib.util.spec_from_loader("garden_scan", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


scan = load_scan()


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return r.stdout


def init_repo(path: Path, email: str = "me@x.com") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", email)
    git(path, "config", "user.name", "Test")
    return path


class RootValidationTests(unittest.TestCase):
    def test_home_rejected(self):
        self.assertFalse(g.validate_root(str(Path.home())))
        self.assertFalse(g.validate_root("~"))

    def test_path_outside_home_rejected(self):
        self.assertFalse(g.validate_root("/tmp"))
        self.assertFalse(g.validate_root("/"))


class GitCommitSignalTests(unittest.TestCase):
    def test_pushed_commit_still_counts(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = init_repo(Path(raw) / "work")
            (repo / "a.py").write_text("x\n", encoding="utf-8")
            git(repo, "add", "a.py")
            git(repo, "commit", "-m", "hello")
            bare = Path(raw) / "bare.git"
            git(Path(raw), "init", "--bare", str(bare))
            git(repo, "remote", "add", "origin", str(bare))
            git(repo, "push", "-u", "origin", "main")
            settings = g.normalize_settings({"authorEmails": ["me@x.com"], "sources": {"git": True}})
            events = scan.git_commit_events(repo, settings, "2000-01-01")
            self.assertTrue(events, "pushed commit must still light a slot")
            self.assertEqual(events[0]["type"], "git")

    def test_vault_backup_skipped(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = init_repo(Path(raw) / "work")
            (repo / "a.py").write_text("x\n", encoding="utf-8")
            git(repo, "add", "a.py")
            git(repo, "commit", "-m", "vault backup: 2026-09-04 23:57:18")
            settings = g.normalize_settings({"authorEmails": ["me@x.com"]})
            events = scan.git_commit_events(repo, settings, "2000-01-01")
            self.assertEqual(events, [])

    def test_other_author_skipped(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = init_repo(Path(raw) / "work", email="other@x.com")
            (repo / "a.py").write_text("x\n", encoding="utf-8")
            git(repo, "add", "a.py")
            git(repo, "commit", "-m", "not mine")
            settings = g.normalize_settings({"authorEmails": ["me@x.com"]})
            events = scan.git_commit_events(repo, settings, "2000-01-01")
            self.assertEqual(events, [])

    def test_author_substring_does_not_match(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = init_repo(Path(raw) / "work", email="andev@x.com")
            (repo / "a.py").write_text("x\n", encoding="utf-8")
            git(repo, "add", "a.py")
            git(repo, "commit", "-m", "not a substring hit")
            settings = g.normalize_settings({"authorEmails": ["dev@x.com"]})
            events = scan.git_commit_events(repo, settings, "2000-01-01")
            self.assertEqual(events, [])


class FileSignalTests(unittest.TestCase):
    def test_non_git_dir_counts_source_not_node_modules(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "app.py").write_text("print(1)\n", encoding="utf-8")
            nm = root / "node_modules"
            nm.mkdir()
            (nm / "pkg.js").write_text("x\n", encoding="utf-8")
            os.utime(root / "app.py", (time.time(), time.time()))
            events = scan.file_events_dir(root, since_ts=0)
            paths = {e["path"] for e in events}
            self.assertTrue(any(p.endswith("app.py") for p in paths), paths)
            self.assertFalse(any("node_modules" in p for p in paths), paths)

    def test_untracked_source_in_git_repo_counts(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = init_repo(Path(raw) / "work")
            (repo / "tracked.py").write_text("a\n", encoding="utf-8")
            git(repo, "add", "tracked.py")
            git(repo, "commit", "-m", "base")
            (repo / "sketch.py").write_text("b\n", encoding="utf-8")
            (repo / "node_modules").mkdir()
            (repo / "node_modules" / "foo.js").write_text("z\n", encoding="utf-8")
            git(repo, "status", "--short")  # node_modules untracked unless gitignored
            (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
            events = scan.file_events(repo, since_ts=0)
            paths = {e["path"] for e in events}
            self.assertIn("sketch.py", paths)
            self.assertIn("tracked.py", paths)
            self.assertFalse(any("node_modules" in p for p in paths), paths)

    def test_png_in_git_repo_does_not_count(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = init_repo(Path(raw) / "work")
            (repo / "a.py").write_text("x\n", encoding="utf-8")
            (repo / "shot.png").write_bytes(b"\x89PNG\r\n")
            git(repo, "add", "a.py", "shot.png")
            git(repo, "commit", "-m", "assets")
            events = scan.file_events(repo, since_ts=0)
            paths = {e["path"] for e in events}
            self.assertIn("a.py", paths)
            self.assertNotIn("shot.png", paths)


if __name__ == "__main__":
    unittest.main()
