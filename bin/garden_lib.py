"""Garden activity math and settings. No I/O except path validation."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

SLOT_MINUTES = 30
SLOTS_PER_DAY = 24 * 60 // SLOT_MINUTES  # 48
MAX_FILE_BYTES = 2 * 1024 * 1024
CODE_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".qml", ".rs", ".go", ".c", ".h", ".cpp",
    ".java", ".kt", ".rb", ".php", ".swift", ".cs", ".sh", ".zsh", ".bash", ".md",
    ".json", ".toml", ".yml", ".yaml", ".css", ".html", ".vue", ".svelte", ".sql",
    ".graphql",
}
DEFAULT_IGNORE_SUBJECT = r"^vault backup:"
DEFAULT_SETTINGS: Dict[str, Any] = {
    "roots": ["~/Projects"],
    "excludeRepos": [],
    "ignoreSubject": DEFAULT_IGNORE_SUBJECT,
    "authorEmails": [],
    "sources": {"files": True, "git": True, "agents": False},
    "slotMinutes": SLOT_MINUTES,
}


def event_slot(day: str, hour: int, minute: int, source: str = "", slot_minutes: int = SLOT_MINUTES) -> tuple:
    index = (hour * 60 + minute) // slot_minutes
    return (day, index)


def union_slots(slots: Iterable[tuple]) -> Set[tuple]:
    return set(slots)


def hours_active(slot_count: int, slot_minutes: int = SLOT_MINUTES) -> float:
    return slot_count * slot_minutes / 60.0


def day_level(slot_count: int) -> int:
    n = int(slot_count or 0)
    if n <= 0:
        return 0
    if n <= 1:
        return 1
    if n <= 3:
        return 2
    if n <= 7:
        return 3
    return 4


def ignore_subject(subject: str, pattern: str = DEFAULT_IGNORE_SUBJECT) -> bool:
    try:
        return bool(re.search(pattern, subject or "", re.I))
    except re.error:
        return False


def author_ok(email: str, allowed: Sequence[str]) -> bool:
    if not allowed:
        return False
    needle = (email or "").strip().lower()
    if not needle:
        return False
    return needle in {e.strip().lower() for e in allowed if e and str(e).strip()}


def git_signal_enabled(settings: Dict[str, Any]) -> bool:
    sources = settings.get("sources") or {}
    if sources.get("git") is False:
        return False
    return bool(settings.get("authorEmails"))


def _expand(raw: str) -> Path:
    return Path(str(raw)).expanduser()


def validate_root(raw: str) -> bool:
    try:
        path = _expand(raw).resolve()
    except Exception:
        return False
    home = Path.home().resolve()
    if path == home:
        return False
    if not path.is_dir():
        return False
    try:
        path.relative_to(home)
    except ValueError:
        return False
    return True


def normalize_settings(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = dict(DEFAULT_SETTINGS)
    data["sources"] = dict(DEFAULT_SETTINGS["sources"])
    if not isinstance(raw, dict):
        return data
    if "roots" in raw:
        if isinstance(raw["roots"], list):
            data["roots"] = [str(x) for x in raw["roots"] if str(x).strip()]
        else:
            data["roots"] = []
    if "excludeRepos" in raw and isinstance(raw["excludeRepos"], list):
        data["excludeRepos"] = [str(x) for x in raw["excludeRepos"]]
    if isinstance(raw.get("ignoreSubject"), str) and raw["ignoreSubject"]:
        data["ignoreSubject"] = raw["ignoreSubject"]
    if "authorEmails" in raw and isinstance(raw["authorEmails"], list):
        data["authorEmails"] = [str(x).strip() for x in raw["authorEmails"] if str(x).strip()]
    if isinstance(raw.get("sources"), dict):
        for key in ("files", "git", "agents"):
            if key in raw["sources"]:
                data["sources"][key] = bool(raw["sources"][key])
    data["slotMinutes"] = SLOT_MINUTES
    return data


def timestamp_slot(ts: float, slot_minutes: int = SLOT_MINUTES) -> tuple:
    local = datetime.fromtimestamp(ts)
    day = local.strftime("%Y-%m-%d")
    return event_slot(day, local.hour, local.minute, slot_minutes=slot_minutes)


def file_since_ts(last_sample: float, midnight: float) -> float:
    """Never jump to midnight if we already sampled yesterday evening."""
    if last_sample > 0:
        return float(last_sample)
    return float(midnight)


def is_code_file(path: Path) -> bool:
    return path.suffix.lower() in CODE_SUFFIXES


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _monday_on_or_before(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _fmt_hhmm(total_minutes: int) -> str:
    total_minutes = max(0, min(24 * 60, int(total_minutes)))
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _fmt_hours(hours: float) -> str:
    if hours == int(hours):
        return str(int(hours))
    return f"{hours:g}"


def collect_review(days: Sequence[Dict[str, Any]], today: date, min_active_days: int = 7) -> Optional[Dict[str, Any]]:
    """Encouragement payload, or None until there are enough lit days."""
    by_day: Dict[str, Set[int]] = {}
    for row in days:
        iso = str(row.get("day") or "")
        slots = row.get("slots") or ()
        if not iso:
            continue
        cleaned = {int(s) for s in slots if isinstance(s, int) or (isinstance(s, str) and str(s).isdigit())}
        if cleaned:
            by_day.setdefault(iso, set()).update(cleaned)
    if len(by_day) < min_active_days:
        return None

    weekday_hits = [0] * 7
    slot_hits: Dict[int, int] = {}
    for iso, slots in by_day.items():
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        weekday_hits[d.weekday()] += 1
        for slot in slots:
            slot_hits[slot] = slot_hits.get(slot, 0) + 1

    peak_wd = max(range(7), key=lambda i: (weekday_hits[i], -i))
    peak_slot = max(slot_hits, key=lambda s: (slot_hits[s], -s))
    this_mon = _monday_on_or_before(today)
    last_mon = this_mon - timedelta(days=7)

    def hours_between(start: date, end: date) -> float:
        n = 0
        cursor = start
        while cursor < end:
            n += len(by_day.get(cursor.isoformat(), ()))
            cursor += timedelta(days=1)
        return hours_active(n)

    h_this = hours_between(this_mon, this_mon + timedelta(days=7))
    h_last = hours_between(last_mon, this_mon)
    start_m = peak_slot * SLOT_MINUTES
    wd = WEEKDAYS[peak_wd]
    sentence = (
        f"{_fmt_hours(h_this)}h this week on this Omarchy box. "
        f"You show up on {wd}s. Around {_fmt_hhmm(start_m)}–{_fmt_hhmm(start_m + SLOT_MINUTES)}."
    )
    return {
        "peakWeekday": wd,
        "peakSlot": peak_slot,
        "hoursThisWeek": h_this,
        "hoursLastWeek": h_last,
        "sentence": sentence,
        "activeDays": len(by_day),
    }


def retain_events(events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return list(events)


_OBSERVED = ("file", "agent")
_KINDS = ("file", "git", "agent")
_WEEKDAY_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_WEEK_COMMIT_CAP = 8
_PROJECT_COMMIT_CAP = 5
_PROJECT_WINDOW_CAP = 8


def _clock(slot: int) -> str:
    return _fmt_hhmm(slot * SLOT_MINUTES)


def _clock_end(slot: int) -> str:
    return _fmt_hhmm((slot + 1) * SLOT_MINUTES)


def _parse_event(raw: Any) -> Optional[tuple]:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("type")
    if kind not in _KINDS:
        return None
    day = raw.get("day")
    if not isinstance(day, str):
        return None
    try:
        when = date.fromisoformat(day)
    except ValueError:
        return None
    slot = raw.get("slot")
    if isinstance(slot, bool) or not isinstance(slot, int):
        return None
    if slot < 0 or slot >= SLOTS_PER_DAY:
        return None
    repo = raw.get("repo")
    repo_name = repo.strip() if isinstance(repo, str) else ""
    digest = raw.get("hash")
    subject = raw.get("subject")
    path = raw.get("path")
    path_name = ""
    if isinstance(path, str) and path.strip():
        path_name = path.strip().replace("\\", "/").rsplit("/", 1)[-1]
    return (
        when,
        slot,
        kind,
        repo_name,
        digest.strip() if isinstance(digest, str) else "",
        subject.strip() if isinstance(subject, str) else "",
        path_name,
    )


def _windows_for(day: date, slot_kinds: Dict[int, Set[str]]) -> List[Dict[str, Any]]:
    if not slot_kinds:
        return []
    ordered = sorted(slot_kinds)
    runs: List[tuple] = []
    start = prev = ordered[0]
    kinds = set(slot_kinds[start])
    for slot in ordered[1:]:
        if slot == prev + 1:
            prev = slot
            kinds.update(slot_kinds[slot])
            continue
        runs.append((start, prev, kinds))
        start = prev = slot
        kinds = set(slot_kinds[slot])
    runs.append((start, prev, kinds))
    windows = []
    for start_slot, end_slot, run_kinds in runs:
        windows.append({
            "day": day.isoformat(),
            "weekday": _WEEKDAY_SHORT[day.weekday()],
            "startSlot": start_slot,
            "endSlot": end_slot,
            "label": f"{_clock(start_slot)}-{_clock_end(end_slot)}",
            "sources": [kind for kind in _KINDS if kind in run_kinds],
        })
    return windows


def _deduped_commits(rows: Sequence[tuple]) -> List[tuple]:
    by_hash: Dict[str, tuple] = {}
    loose: List[tuple] = []
    for row in rows:
        if row[2] != "git":
            continue
        digest = row[4]
        if not digest:
            loose.append(row)
            continue
        previous = by_hash.get(digest)
        if previous is None or (row[0], row[1]) >= (previous[0], previous[1]):
            by_hash[digest] = row
    commits = list(by_hash.values()) + loose
    commits.sort(key=lambda row: (row[0], row[1], row[4]), reverse=True)
    return commits


def _commit_payload(row: tuple) -> Dict[str, Any]:
    return {
        "day": row[0].isoformat(),
        "slot": row[1],
        "label": _clock(row[1]),
        "hash": row[4],
        "subject": row[5],
        "repo": row[3],
    }


def _same_run(left: Dict[str, Set[str]], right: Dict[str, Set[str]]) -> bool:
    return left["projects"] == right["projects"] and left["sources"] == right["sources"]


def _week_spans(rows: Sequence[tuple], week_start: date, today: date) -> List[Dict[str, Any]]:
    by_day: Dict[date, Dict[int, Dict[str, Set[str]]]] = {}
    for when, slot, kind, repo, _digest, _subject, _path in rows:
        if when < week_start or when > today:
            continue
        cell = by_day.setdefault(when, {}).setdefault(slot, {"projects": set(), "sources": set()})
        cell["sources"].add(kind)
        if repo:
            cell["projects"].add(repo)
    spans: List[Dict[str, Any]] = []
    for when in sorted(by_day):
        ordered = sorted(by_day[when])
        start = prev = ordered[0]
        current = by_day[when][start]
        for slot in ordered[1:]:
            cell = by_day[when][slot]
            if slot == prev + 1 and _same_run(current, cell):
                prev = slot
                continue
            spans.append(_span_payload(when, start, prev, current))
            start = prev = slot
            current = cell
        spans.append(_span_payload(when, start, prev, current))
    return spans


def _span_payload(when: date, start_slot: int, end_slot: int, cell: Dict[str, Set[str]]) -> Dict[str, Any]:
    return {
        "day": when.isoformat(),
        "weekday": _WEEKDAY_SHORT[when.weekday()],
        "startSlot": start_slot,
        "endSlot": end_slot,
        "label": f"{_clock(start_slot)}-{_clock_end(end_slot)}",
        "projects": sorted(cell["projects"]),
        "sources": [kind for kind in _KINDS if kind in cell["sources"]],
    }


def _attach_also(projects: List[Dict[str, Any]], rows: Sequence[tuple]) -> None:
    present: Dict[tuple, Set[str]] = {}
    for when, slot, _kind, repo, _digest, _subject, _path in rows:
        if repo:
            present.setdefault((when, slot), set()).add(repo)
    for project in projects:
        for window in project["windows"]:
            when = date.fromisoformat(window["day"])
            others: Set[str] = set()
            for slot in range(window["startSlot"], window["endSlot"] + 1):
                others.update(present.get((when, slot), ()))
            others.discard(project["name"])
            window["also"] = sorted(others)


def _project_payload(name: str, rows: Sequence[tuple], limit_windows: Optional[int]) -> Dict[str, Any]:
    by_day: Dict[date, Dict[int, Set[str]]] = {}
    active_days: Set[date] = set()
    last: Optional[tuple] = None
    for row in rows:
        when, slot, kind, _repo, _digest, _subject, _path = row
        by_day.setdefault(when, {}).setdefault(slot, set()).add(kind)
        if kind in _OBSERVED:
            active_days.add(when)
        if last is None or (when, slot) >= (last[0], last[1]):
            last = row
    windows: List[Dict[str, Any]] = []
    for when in sorted(by_day):
        windows.extend(_windows_for(when, by_day[when]))
    if limit_windows is not None and len(windows) > limit_windows:
        windows = windows[-limit_windows:]
    touched = last or rows[0]
    return {
        "name": name,
        "daysActive": len(active_days),
        "lastTouched": {
            "day": touched[0].isoformat(),
            "slot": touched[1],
            "label": _clock(touched[1]),
            "path": touched[6] if touched[2] == "file" else "",
        },
        "windows": windows,
        "recentCommits": [_commit_payload(row) for row in _deduped_commits(rows)[:_PROJECT_COMMIT_CAP]],
    }


def summarize_activity(
    events: Optional[Iterable[Any]],
    today: date,
    coverage: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """This week and projects from ledger events.

    machineHours counts each observed half-hour once.
    Project windows may overlap that total. They are not added into it.
    """
    if isinstance(today, datetime) or not isinstance(today, date):
        raise TypeError("today must be a date")
    week_start = _monday_on_or_before(today)
    week_end = week_start + timedelta(days=6)
    rows: List[tuple] = []
    for raw in events or []:
        parsed = _parse_event(raw)
        if parsed is None or parsed[0] > today:
            continue
        if isinstance(coverage, dict) and coverage.get(parsed[0].isoformat()) == "unknown":
            continue
        rows.append(parsed)

    by_repo: Dict[str, List[tuple]] = {}
    for row in rows:
        if row[3]:
            by_repo.setdefault(row[3], []).append(row)

    def in_week(when: date) -> bool:
        return week_start <= when <= today

    observed: Set[tuple] = set()
    day_slots: Dict[date, Set[int]] = {}
    day_commits: Dict[date, List[tuple]] = {}
    day_projects: Dict[date, Set[str]] = {}
    for row in rows:
        when, slot, kind, repo, _digest, _subject, _path = row
        if repo:
            day_projects.setdefault(when, set()).add(repo)
        if kind == "git":
            day_commits.setdefault(when, []).append(row)
        if kind in _OBSERVED and in_week(when):
            observed.add((when, slot))
            day_slots.setdefault(when, set()).add(slot)

    days_out = []
    for offset in range(7):
        when = week_start + timedelta(days=offset)
        future = when > today
        entry: Dict[str, Any] = {
            "date": when.isoformat(),
            "weekday": _WEEKDAY_SHORT[when.weekday()],
            "future": future,
            "observedSlots": 0 if future else len(day_slots.get(when, ())),
            "commits": 0 if future else len(_deduped_commits(day_commits.get(when, ()))),
            "projects": [] if future else sorted(day_projects.get(when, ())),
        }
        if not future and isinstance(coverage, dict):
            label = coverage.get(when.isoformat())
            if isinstance(label, str) and label:
                entry["coverage"] = label
        days_out.append(entry)

    week_rows = [row for row in rows if in_week(row[0])]
    week_names = sorted({row[3] for row in week_rows if row[3]})
    week_projects = [
        _project_payload(name, [row for row in by_repo[name] if in_week(row[0])], None)
        for name in week_names
    ]
    week_projects.sort(
        key=lambda item: (item["lastTouched"]["day"], item["lastTouched"]["slot"]),
        reverse=True,
    )

    projects = [_project_payload(name, by_repo[name], _PROJECT_WINDOW_CAP) for name in sorted(by_repo)]
    projects.sort(
        key=lambda item: (item["lastTouched"]["day"], item["lastTouched"]["slot"]),
        reverse=True,
    )
    for item in projects:
        item["thisWeek"] = any(in_week(row[0]) for row in by_repo[item["name"]])
    _attach_also(week_projects, rows)
    _attach_also(projects, rows)

    return {
        "week": {
            "start": week_start.isoformat(),
            "end": week_end.isoformat(),
            "daysActive": sum(1 for day in days_out if day["observedSlots"] > 0),
            "machineSlots": len(observed),
            "machineHours": hours_active(len(observed)),
            "days": days_out,
            "spans": _week_spans(rows, week_start, today),
            "projects": week_projects,
            "recentCommits": [_commit_payload(row) for row in _deduped_commits(week_rows)[:_WEEK_COMMIT_CAP]],
        },
        "projects": projects,
    }
