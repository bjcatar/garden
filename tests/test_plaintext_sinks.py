"""Repo and path strings stay literal, and the panel draws them as plain text.

Qt Text defaults to Text.AutoText. A commit subject that looks like an HTML
image tag can then load a URL. PlainText is the boundary. Python keeps the
characters so the week note and the panel show the subject as it was written.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"
sys.path.insert(0, str(BIN))
import garden_lib as g  # noqa: E402

TODAY = date(2026, 10, 24)
IMG_SUBJECT = '<img src="http://127.0.0.1/garden-subject.png">'
IMG_REPO = '<img src="http://127.0.0.1/garden-repo.png">'
IMG_PATH = '<img src="http://127.0.0.1/garden-path.png">'
IMG_DIR = '<img src="http:127.0.0.1">'

# Bindings that carry a repository or filesystem string into a text item.
_MARKERS = (
    "modelData.line",
    "modelData.name",
    "modelData.touched",
    "modelData.display",
    "modelData.stored",
    "modelData.hits",
    ".repos",
    "sheet.subject",
    "fileLabel",
    ".path",
)
_KINDS = (
    "TextEdit",
    "TextField",
    "TextArea",
    "TextInput",
    "PanelToolTip",
    "BarIconButton",
    "Label",
    "Text",
)
_QML = (
    ROOT / "Panel.qml",
    ROOT / "BarWidget.qml",
    ROOT / "tests" / "qml" / "panel-lifecycle.qml",
)


def load_scan():
    path = BIN / "garden-scan"
    loader = importlib.machinery.SourceFileLoader("garden_scan_plaintext", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _skip_string(source: str, start: int) -> int:
    quote = source[start]
    i = start + 1
    while i < len(source):
        if source[i] == "\\":
            i += 2
            continue
        if source[i] == quote:
            return i + 1
        i += 1
    return len(source)


def _match_brace(source: str, open_at: int) -> int:
    depth = 0
    i = open_at
    while i < len(source):
        if source.startswith("//", i):
            nl = source.find("\n", i)
            i = len(source) if nl < 0 else nl + 1
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = len(source) if end < 0 else end + 2
            continue
        ch = source[i]
        if ch in "\"'":
            i = _skip_string(source, i)
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(source)


def _kind_at(source: str, i: int) -> str | None:
    if i > 0 and (source[i - 1].isalnum() or source[i - 1] in "._"):
        return None
    for kind in _KINDS:
        end = i + len(kind)
        if not source.startswith(kind, i):
            continue
        j = end
        while j < len(source) and source[j] in " \t":
            j += 1
        if j < len(source) and source[j] == "{":
            return kind
    return None


class QmlItem:
    def __init__(self, kind: str, start: int, end: int, source: str):
        self.kind = kind
        self.start = start
        self.end = end
        self.source = source

    def line(self, file_text: str) -> int:
        return file_text.count("\n", 0, self.start) + 1


def qml_items(source: str) -> list[QmlItem]:
    items = []
    i = 0
    while i < len(source):
        if source.startswith("//", i):
            nl = source.find("\n", i)
            i = len(source) if nl < 0 else nl + 1
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = len(source) if end < 0 else end + 2
            continue
        if source[i] in "\"'":
            i = _skip_string(source, i)
            continue
        kind = _kind_at(source, i)
        if kind is None:
            i += 1
            continue
        brace = source.find("{", i)
        end = _match_brace(source, brace)
        items.append(QmlItem(kind, i, end, source[i:end]))
        i = end
    return items


def _depth1_slice(item_source: str) -> str:
    brace = item_source.find("{")
    parts = []
    depth = 0
    i = brace
    while i < len(item_source):
        if item_source.startswith("//", i):
            nl = item_source.find("\n", i)
            i = len(item_source) if nl < 0 else nl + 1
            continue
        if item_source.startswith("/*", i):
            end = item_source.find("*/", i + 2)
            i = len(item_source) if end < 0 else end + 2
            continue
        ch = item_source[i]
        if ch in "\"'" and depth >= 1:
            nxt = _skip_string(item_source, i)
            if depth == 1:
                parts.append(item_source[i:nxt])
            i = nxt
            continue
        if ch == "{":
            depth += 1
            if depth == 1:
                parts.append("{")
            i += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                break
            i += 1
            continue
        if depth == 1:
            parts.append(ch)
        i += 1
    return "".join(parts)


def text_binding(item: QmlItem) -> str | None:
    source = item.source
    brace = source.find("{")
    depth = 0
    i = brace
    token = "text:"
    while i < len(source):
        if source.startswith("//", i):
            nl = source.find("\n", i)
            i = len(source) if nl < 0 else nl + 1
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = len(source) if end < 0 else end + 2
            continue
        ch = source[i]
        if ch in "\"'":
            i = _skip_string(source, i)
            continue
        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return None
            i += 1
            continue
        if depth == 1 and source.startswith(token, i):
            prev = source[i - 1] if i else ""
            if not (prev.isalnum() or prev in "._"):
                j = i + len(token)
                while j < len(source) and source[j] in " \t":
                    j += 1
                if j < len(source) and source[j] == "{":
                    end = _match_brace(source, j)
                    return source[j:end]
                line_end = source.find("\n", j)
                if line_end < 0:
                    line_end = len(source)
                return source[j:line_end].strip()
        i += 1
    return None


def _untrusted(binding: str | None, prefix: str) -> bool:
    if binding is None:
        return False
    if any(marker in binding for marker in _MARKERS):
        return True
    if binding.strip() == "modelData":
        window = prefix[-2000:]
        return window.rfind("openRepos") > window.rfind("WEEKDAY_LABELS")
    return False


def untrusted_items(path: Path) -> list[tuple[int, QmlItem, str]]:
    file_text = path.read_text(encoding="utf-8")
    found = []
    for item in qml_items(file_text):
        binding = text_binding(item)
        if _untrusted(binding, file_text[:item.start]):
            found.append((item.line(file_text), item, binding or ""))
    return found


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class PlainTextSinkTests(unittest.TestCase):
    maxDiff = None

    def test_repo_text_sinks_use_plain_text(self):
        panel = untrusted_items(ROOT / "Panel.qml")
        self.assertEqual(
            len(panel),
            13,
            "\n".join(f"{line}: {binding[:80]}" for line, _item, binding in panel),
        )
        missing = [
            f"{line}: {binding[:80]}"
            for line, item, binding in panel
            if "textFormat: Text.PlainText" not in _depth1_slice(item.source)
        ]
        self.assertEqual(missing, [])
        for path in _QML:
            for _line, item, _binding in untrusted_items(path):
                own = _depth1_slice(item.source)
                for rich in ("Text.AutoText", "Text.RichText", "Text.StyledText", "Text.MarkdownText"):
                    self.assertNotIn(rich, own)

    def test_other_qml_has_no_repo_text_sink(self):
        for path in _QML:
            if path.name == "Panel.qml":
                continue
            self.assertEqual(untrusted_items(path), [], path.name)

    def test_heatmap_tooltip_does_not_bind_repo_strings(self):
        file_text = (ROOT / "Panel.qml").read_text(encoding="utf-8")
        tips = [item for item in qml_items(file_text) if item.kind == "PanelToolTip"]
        self.assertEqual(len(tips), 1)
        binding = text_binding(tips[0]) or ""
        for marker in ("repos", "subject", "fileLabel", ".path", ".name", "modelData.line"):
            self.assertNotIn(marker, binding)

    def test_markup_stays_literal_in_panel_lines_and_copy(self):
        events = [
            {
                "type": "git",
                "day": "2026-10-24",
                "slot": 20,
                "repo": IMG_REPO,
                "hash": "abc",
                "subject": IMG_SUBJECT,
            },
            {
                "type": "file",
                "day": "2026-10-24",
                "slot": 21,
                "repo": IMG_REPO,
                "path": IMG_PATH,
            },
        ]
        out = g.summarize_activity(events, TODAY)
        week = out["week"]
        commit_line = week["recentCommits"][0]["line"]
        self.assertTrue(commit_line.startswith(IMG_SUBJECT), commit_line)
        self.assertIn(IMG_REPO, commit_line)
        span_text = "\n".join(span["line"] for span in week["spans"])
        self.assertIn(IMG_REPO, span_text)
        self.assertIn(IMG_PATH, span_text)
        self.assertEqual(out["projects"][0]["name"], IMG_REPO)
        self.assertIn(IMG_PATH, out["projects"][0]["touched"])
        self.assertIn(IMG_SUBJECT, out["projects"][0]["recentCommits"][0]["line"])
        for copy in (week["markdown"], week["resume"]):
            self.assertIn(IMG_SUBJECT, copy)
            self.assertIn(IMG_REPO, copy)
            self.assertIn(IMG_PATH, copy)
            self.assertNotIn("&lt;", copy)
            self.assertNotIn("&gt;", copy)

    def test_markup_repo_stays_on_the_year_day(self):
        day = g.cover_days(
            [{
                "type": "git",
                "day": "2026-10-24",
                "slot": 20,
                "hash": "abc",
                "repo": IMG_REPO,
                "subject": IMG_SUBJECT,
            }],
            g.parse_scan_state({}),
            TODAY,
            TODAY,
        )["2026-10-24"]
        self.assertIn(IMG_REPO, day.repos)
        self.assertIn(IMG_REPO, day.by_slot["20"]["repos"])
        self.assertNotIn(IMG_SUBJECT, day.label)
        self.assertNotIn(IMG_REPO, day.label)

    def test_markup_settings_path_and_pattern_stay_literal(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            folder = home / IMG_DIR
            folder.mkdir()
            sheet = g.settings_sheet(
                {"roots": [str(folder)], "ignoreSubject": IMG_SUBJECT, "excludeRepos": [IMG_DIR]},
                [{"label": IMG_DIR, "path": str(folder), "name": IMG_DIR}],
                {"version": "0.3.1"},
                home=home,
            )
        self.assertIn(IMG_DIR, sheet["roots"][0]["display"])
        self.assertEqual(sheet["subject"]["pattern"], IMG_SUBJECT)
        self.assertEqual(sheet["mutes"][0]["stored"], IMG_DIR)
        self.assertIn(IMG_DIR, sheet["mutes"][0]["hits"])
        self.assertNotIn("&lt;", sheet["roots"][0]["display"])

    def test_scan_keeps_a_markup_subject_for_the_panel(self):
        scan = load_scan()
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw) / "work"
            repo.mkdir()
            _git(repo, "init", "-b", "main")
            _git(repo, "config", "user.email", "me@x.com")
            _git(repo, "config", "user.name", "Test")
            (repo / "a.py").write_text("x\n", encoding="utf-8")
            _git(repo, "add", "a.py")
            _git(repo, "commit", "-m", IMG_SUBJECT)
            settings = g.normalize_settings({"authorEmails": ["me@x.com"], "sources": {"git": True}})
            events = scan.git_commit_events(repo, settings, "2000-01-01")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["subject"], IMG_SUBJECT)
        week = g.summarize_activity(events, date.today())["week"]
        self.assertTrue(week["recentCommits"][0]["line"].startswith(IMG_SUBJECT))
        self.assertIn(IMG_SUBJECT, week["markdown"])
        self.assertIn(IMG_SUBJECT, week["resume"])


if __name__ == "__main__":
    unittest.main()
