"""Garden activity math, settings, and scan coverage.

Path validation checks directories. The coverage functions do not start processes or read files.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, Set

SLOT_MINUTES = 30
SLOTS_PER_DAY = 24 * 60 // SLOT_MINUTES  # 48
HEATMAP_FRESH_SECONDS = 15 * 60
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


HARD_SKIP_NOTE = "Build and dependency folders are skipped by the scanner. They are not mutes."


@dataclass(frozen=True)
class RootDecision:
    """Accept stores an absolute path. Home and reject leave stored and display empty."""

    kind: Literal["accept", "home", "reject"]
    stored: str
    display: str
    token: str
    offers: tuple[tuple[str, str], ...]

    @property
    def ok(self) -> bool:
        return self.kind == "accept"


def _with_home_prefix(text: str, prefix: str, home: Path) -> Optional[Path]:
    if text == prefix:
        return home
    for sep in ("/", os.sep):
        marker = prefix + sep
        if text.startswith(marker):
            rest = text[len(marker):].lstrip("/\\")
            return home / rest if rest else home
    return None


def expand_root(raw: str, home: Path) -> Path:
    """Map a leading $HOME, ${HOME}, or ~ onto home. Leave other variables alone."""
    text = "" if raw is None else str(raw).strip()
    base = Path(home)
    for prefix in ("${HOME}", "$HOME"):
        mapped = _with_home_prefix(text, prefix, base)
        if mapped is not None:
            return mapped
    if text == "~":
        return base
    if text.startswith("~/") or (os.sep != "/" and text.startswith("~" + os.sep)):
        rest = text[2:] if text.startswith("~/") else text[1 + len(os.sep):]
        rest = rest.lstrip("/\\")
        return base / rest if rest else base
    if text.startswith("~"):
        return Path(text).expanduser()
    path = Path(text)
    if path.is_absolute():
        return path
    return base / text


def display_path(path: str | Path, home: Path) -> str:
    home_s = str(home)
    rel = str(path)
    if rel.startswith(home_s + os.sep):
        return "~" + rel[len(home_s):]
    return rel


def _classify(raw: str, home: Path) -> RootDecision:
    text = "" if raw is None else str(raw).strip()
    if not text:
        return RootDecision("reject", "", "", "empty", ())
    try:
        expanded = expand_root(text, home).resolve()
        resolved_home = Path(home).resolve()
    except (OSError, RuntimeError, ValueError):
        return RootDecision("reject", "", "", "missing", ())
    if expanded == resolved_home:
        return RootDecision("home", "", "", "home", ())
    if not expanded.exists():
        return RootDecision("reject", "", "", "missing", ())
    if not expanded.is_dir():
        return RootDecision("reject", "", "", "not-directory", ())
    try:
        expanded.relative_to(resolved_home)
    except ValueError:
        return RootDecision("reject", "", "", "outside-home", ())
    stored = str(expanded)
    return RootDecision("accept", stored, display_path(stored, resolved_home), "", ())


def _pin_name() -> str:
    roots = DEFAULT_SETTINGS.get("roots") or []
    if not roots:
        return ""
    return Path(str(roots[0])).name


def _direct_offers(home: Path) -> tuple[tuple[str, str], ...]:
    pin = _pin_name()
    found: List[tuple[str, str, str]] = []
    try:
        children = list(Path(home).iterdir())
    except OSError:
        return ()
    for child in children:
        name = child.name
        if not name or name.startswith("."):
            continue
        try:
            decision = _classify(str(child), home)
        except (OSError, RuntimeError, ValueError):
            continue
        if not decision.ok:
            continue
        found.append((name, decision.stored, decision.display))
    found.sort(key=lambda row: (row[0] != pin, row[0].casefold()))
    return tuple((stored, display) for name, stored, display in found)


def root_decision(raw: str, *, home: Optional[Path] = None) -> RootDecision:
    base = Path.home() if home is None else Path(home)
    decision = _classify(raw, base)
    if decision.kind != "home":
        return decision
    try:
        resolved_home = base.resolve()
    except (OSError, RuntimeError, ValueError):
        return RootDecision("home", "", "", "home", ())
    return RootDecision("home", "", "", "home", _direct_offers(resolved_home))


def validate_root(raw: str) -> bool:
    return root_decision(raw).ok


def repo_muted(label: str, path: str, name: str, exclude: Sequence[str]) -> bool:
    for item in exclude:
        if item in (label, path, name):
            return True
    return False


def manifest_version(manifest: Optional[Mapping[str, Any]]) -> str:
    if not isinstance(manifest, Mapping):
        return ""
    version = manifest.get("version")
    if isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version):
        return version
    return ""


def _copy_settings(settings: Mapping[str, Any]) -> Dict[str, Any]:
    data = dict(settings)
    roots = data.get("roots")
    data["roots"] = list(roots) if isinstance(roots, list) else []
    exclude = data.get("excludeRepos")
    if isinstance(exclude, list):
        data["excludeRepos"] = list(exclude)
    sources = data.get("sources")
    if isinstance(sources, dict):
        data["sources"] = dict(sources)
    return data


def _same_directory(left: str, right: str, home: Path) -> bool:
    try:
        a = expand_root(left, home).resolve()
        b = expand_root(right, home).resolve()
        return a == b and a.is_dir()
    except (OSError, RuntimeError, ValueError):
        return False


def apply_add_root(settings: Mapping[str, Any], raw: str, *, home: Path) -> Dict[str, Any]:
    data = _copy_settings(settings)
    roots = data["roots"]
    text = "" if raw is None else str(raw)
    decision = root_decision(text, home=home)
    if not decision.ok:
        return data
    stripped = text.strip()
    if text in roots or stripped in roots:
        return data
    for existing in roots:
        existing_text = str(existing)
        if existing_text == decision.stored or _same_directory(existing_text, text, home):
            return data
    roots.append(decision.stored)
    data["roots"] = roots
    return data


def apply_remove_root(settings: Mapping[str, Any], raw: str, *, home: Path) -> Dict[str, Any]:
    data = _copy_settings(settings)
    text = "" if raw is None else str(raw)
    try:
        expanded = str(expand_root(text, home))
    except (OSError, RuntimeError, ValueError):
        expanded = ""
    kept: List[Any] = []
    for existing in data["roots"]:
        existing_text = str(existing)
        if existing_text == text or (expanded and existing_text == expanded):
            continue
        if text and _same_directory(existing_text, text, home):
            continue
        kept.append(existing)
    data["roots"] = kept
    return data


def apply_mute(settings: Mapping[str, Any], raw: str, mute: bool) -> Dict[str, Any]:
    data = _copy_settings(settings)
    exclude = data.get("excludeRepos")
    items = [str(item) for item in exclude] if isinstance(exclude, list) else []
    text = "" if raw is None else str(raw)
    if mute:
        if text.strip() and text not in items:
            items.append(text)
    else:
        items = [item for item in items if item != text]
    data["excludeRepos"] = items
    return data


def _repo_bits(repo: Mapping[str, Any]) -> tuple[str, str, str, str]:
    path = str(repo.get("path") or "")
    name = str(repo.get("name") or "")
    if not name and path:
        name = Path(path).name
    label = str(repo.get("label") or "")
    shown = label if label else path
    return label, path, name, shown


def settings_sheet(
    settings: Mapping[str, Any],
    repos: Sequence[Mapping[str, Any]],
    manifest: Optional[Mapping[str, Any]],
    *,
    home: Path,
    force_offers: bool = False,
) -> Dict[str, Any]:
    raw = dict(settings) if isinstance(settings, Mapping) else None
    normalized = normalize_settings(raw)
    base = Path(home)
    roots_out: List[Dict[str, Any]] = []
    any_ok = False
    for stored in normalized.get("roots") or []:
        stored_text = str(stored)
        decision = root_decision(stored_text, home=base)
        any_ok = any_ok or decision.ok
        roots_out.append({
            "stored": stored_text,
            "display": decision.display,
            "ok": decision.ok,
            "token": decision.token,
        })
    if force_offers or not any_ok:
        try:
            offers = _direct_offers(base.resolve())
        except (OSError, RuntimeError, ValueError):
            offers = ()
    else:
        offers = ()
    exclude = [str(item) for item in (normalized.get("excludeRepos") or [])]
    repo_rows = [repo for repo in (repos or []) if isinstance(repo, Mapping)]
    mutes: List[Dict[str, Any]] = []
    for item in exclude:
        hits: List[str] = []
        for repo in repo_rows:
            label, path, name, shown = _repo_bits(repo)
            if repo_muted(label, path, name, [item]) and shown:
                hits.append(shown)
        mutes.append({"stored": item, "hits": hits})
    open_repos: List[str] = []
    for repo in repo_rows:
        label, path, name, shown = _repo_bits(repo)
        if shown and not repo_muted(label, path, name, exclude):
            open_repos.append(shown)
    pattern = str(normalized.get("ignoreSubject") or DEFAULT_IGNORE_SUBJECT)
    return {
        "version": manifest_version(manifest),
        "roots": roots_out,
        "offers": [{"stored": stored, "display": display} for stored, display in offers],
        "mutes": mutes,
        "openRepos": open_repos,
        "subject": {"pattern": pattern, "isDefault": pattern == DEFAULT_IGNORE_SUBJECT},
        "hardSkipNote": HARD_SKIP_NOTE,
    }


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

    def slots_between(start: date, end: date) -> int:
        n = 0
        cursor = start
        while cursor < end:
            n += len(by_day.get(cursor.isoformat(), ()))
            cursor += timedelta(days=1)
        return n

    slots_this = slots_between(this_mon, this_mon + timedelta(days=7))
    h_this = hours_active(slots_this)
    h_last = hours_active(slots_between(last_mon, this_mon))
    start_m = peak_slot * SLOT_MINUTES
    wd = WEEKDAYS[peak_wd]
    sentence = (
        f"{week_clause(slots_this)}. "
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


_DOT = " \u00b7 "


def _hour_text(hours: float) -> str:
    whole = int(hours)
    if hours == whole:
        return str(whole)
    return str(hours)


def _day_caption(day: Mapping[str, Any]) -> str:
    if day.get("future"):
        return ""
    coverage = day.get("coverage") or ""
    observed = day.get("observedSlots") or 0
    if coverage in ("unknown", "gap"):
        return ""
    if coverage == "sampled" and observed <= 0:
        return ""
    if coverage and coverage not in ("observed", "empty", "sampled"):
        return ""
    if observed <= 0:
        return ""
    return _hour_text(hours_active(observed))


def _window_line(item: Mapping[str, Any]) -> str:
    sources = list(item.get("sources") or [])
    line = f"{item.get('weekday') or ''} {item.get('label') or ''}"
    names = list(item.get("projects") or [])
    if names:
        line += _DOT + ", ".join(names)
    if len(sources) == 1 and sources[0] == "git":
        line += _DOT + "commit only"
    elif not names and "agent" in sources:
        line += _DOT + "agent"
    also = list(item.get("also") or [])
    if also:
        line += _DOT + "also " + ", ".join(also)
    return line


def _commit_line(item: Mapping[str, Any]) -> str:
    bits = [item.get("subject") or item.get("hash") or "commit"]
    if item.get("repo"):
        bits.append(item["repo"])
    if item.get("label"):
        bits.append(item["label"])
    return _DOT.join(bits)


def _touched_line(project: Mapping[str, Any]) -> str:
    touched = project.get("lastTouched")
    if not touched:
        return ""
    when = f"Last touched {touched.get('day') or ''} {touched.get('label') or ''}"
    if touched.get("path"):
        when += _DOT + touched["path"]
    days = project.get("daysActive") or 0
    if not days:
        return when
    noun = "day" if days == 1 else "days"
    return f"{when}{_DOT}{days} {noun} active"


def _week_headline(days_active: int, machine_hours: float) -> str:
    if days_active == 0 and machine_hours == 0:
        return "No observed time on this machine this week"
    noun = "day" if days_active == 1 else "days"
    return f"{days_active} {noun} active{_DOT}{_hour_text(machine_hours)}h on this machine"


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
        entry["caption"] = _day_caption(entry)
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

    spans = _week_spans(rows, week_start, today)
    for span in spans:
        span["line"] = _window_line(span)
    recent = [_commit_payload(row) for row in _deduped_commits(week_rows)[:_WEEK_COMMIT_CAP]]
    for item in recent:
        item["line"] = _commit_line(item)
    for project in week_projects:
        project["touched"] = _touched_line(project)
        for window in project["windows"]:
            window["line"] = _window_line(window)
    for project in projects:
        project["touched"] = _touched_line(project)
        for window in project["windows"]:
            window["line"] = _window_line(window)
        for item in project["recentCommits"]:
            item["line"] = _commit_line(item)

    days_active = sum(1 for day in days_out if day["observedSlots"] > 0)
    machine_hours = hours_active(len(observed))

    def week_note(report: Dict[str, Any]) -> str:
        blocks = [
            "# This week",
            f"{report['start']} to {report['end']}",
            report["headline"],
            report["overlap"],
            "## Days",
        ]
        day_lines = []
        for day in report["days"]:
            caption = day["caption"]
            if caption:
                day_lines.append(f"{day['weekday']} {day['date']}. {caption}h")
            else:
                day_lines.append(f"{day['weekday']} {day['date']}.")
        blocks.append("\n".join(day_lines))
        if report["spans"]:
            blocks.append("## Windows")
            blocks.append("\n".join(span["line"] for span in report["spans"]))
        if report["recentCommits"]:
            blocks.append("## Recent commits")
            blocks.append("\n".join(item["line"] for item in report["recentCommits"]))
        if report["projects"]:
            blocks.append("## Projects")
            for project in report["projects"]:
                blocks.append(f"### {project['name']}")
                lines = [project["touched"]]
                lines.extend(window["line"] for window in project["windows"])
                blocks.append("\n".join(lines))
        blocks.append("## Note")
        return "\n\n".join(blocks) + "\n\n"

    def week_copy_hint(report: Dict[str, Any]) -> str:
        bits = ["Days"]
        project_count = len(report["projects"])
        commit_count = len(report["recentCommits"])
        if project_count == 1:
            bits.append("1 project")
        elif project_count > 1:
            bits.append(f"{project_count} projects")
        if commit_count == 1:
            bits.append("1 recent commit")
        elif commit_count > 1:
            bits.append(f"{commit_count} recent commits")
        bits.append("a blank Note")
        if len(bits) == 2:
            detail = f"{bits[0]} and {bits[1]}"
        else:
            detail = ", ".join(bits[:-1]) + ", and " + bits[-1]
        return f"Markdown note. {report['start']} to {report['end']}. {detail}."

    week = {
        "start": week_start.isoformat(),
        "end": week_end.isoformat(),
        "daysActive": days_active,
        "machineSlots": len(observed),
        "machineHours": machine_hours,
        "headline": _week_headline(days_active, machine_hours),
        "overlap": "Project windows overlap. They are not added into hours on this machine.",
        "days": days_out,
        "spans": spans,
        "projects": week_projects,
        "recentCommits": recent,
    }
    week["markdown"] = week_note(week)
    week["copyHint"] = week_copy_hint(week)
    week["resume"] = resume_markdown(week)
    return {"week": week, "projects": projects}


def week_markdown(week: Mapping[str, Any]) -> str:
    text = week.get("markdown") if isinstance(week, Mapping) else None
    if isinstance(text, str) and text.startswith("# This week\n"):
        return text
    return ""


def heatmap_is_fresh(
    snap: Mapping[str, Any],
    now: datetime,
    *,
    fresh_seconds: int = HEATMAP_FRESH_SECONDS,
) -> bool:
    raw = snap.get("generatedAt") if isinstance(snap, Mapping) else None
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        generated = datetime.fromisoformat(raw.strip())
    except ValueError:
        return False
    if generated.tzinfo is not None or now.tzinfo is not None:
        return False
    age = (now - generated).total_seconds()
    if age < -60:
        return False
    return age <= fresh_seconds


def week_summary(week: Mapping[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "range": {"start": week.get("start"), "end": week.get("end")},
        "daysActive": week.get("daysActive", 0),
    }
    if "machineSlots" in week:
        summary["machineSlots"] = week["machineSlots"]
    if "machineHours" in week:
        summary["machineHours"] = week["machineHours"]
    projects_out: List[Dict[str, Any]] = []
    for project in week.get("projects") or []:
        if not isinstance(project, Mapping):
            continue
        item: Dict[str, Any] = {"name": project.get("name") or ""}
        if "daysActive" in project:
            item["daysActive"] = project["daysActive"]
        item["lastTouched"] = dict(project["lastTouched"]) if isinstance(project.get("lastTouched"), Mapping) else {}
        item["windows"] = [
            _window_fields(window)
            for window in (project.get("windows") or [])
            if isinstance(window, Mapping)
        ]
        projects_out.append(item)
    summary["projects"] = projects_out
    commits = [
        _commit_fields(item)
        for item in (week.get("recentCommits") or [])
        if isinstance(item, Mapping)
    ]
    if commits:
        summary["recentCommits"] = commits
    return summary


def resume_markdown(week: Mapping[str, Any]) -> str:
    blocks = [
        "# Resume",
        f"{week.get('start') or ''} to {week.get('end') or ''}",
    ]
    headline = week.get("headline")
    if isinstance(headline, str) and headline:
        blocks.append(headline)
    project_lines: List[str] = []
    for project in week.get("projects") or []:
        if not isinstance(project, Mapping):
            continue
        name = str(project.get("name") or "")
        touched = project.get("touched") if isinstance(project.get("touched"), str) else ""
        if not touched:
            touched = _touched_line(project)
        head = f"{name}{_DOT}{touched}" if name and touched else (name or touched)
        if head:
            project_lines.append(head)
        for window in project.get("windows") or []:
            if not isinstance(window, Mapping):
                continue
            line = window.get("line") if isinstance(window.get("line"), str) and window.get("line") else _window_line(window)
            if line:
                project_lines.append(line)
    if project_lines:
        blocks.append("## Projects\n" + "\n".join(project_lines))
    commit_lines: List[str] = []
    for item in week.get("recentCommits") or []:
        if not isinstance(item, Mapping):
            continue
        line = item.get("line") if isinstance(item.get("line"), str) and item.get("line") else _commit_line(item)
        commit_lines.append(line)
    if commit_lines:
        blocks.append("## Recent commits\n" + "\n".join(commit_lines))
    return "\n\n".join(blocks) + "\n"


def _window_fields(window: Mapping[str, Any]) -> Dict[str, Any]:
    kept: Dict[str, Any] = {}
    for key in ("day", "weekday", "label", "startSlot", "endSlot", "sources", "also"):
        if key in window:
            kept[key] = window[key]
    return kept


def _commit_fields(item: Mapping[str, Any]) -> Dict[str, Any]:
    kept: Dict[str, Any] = {}
    for key in ("day", "slot", "label", "hash", "subject", "repo"):
        if key in item:
            kept[key] = item[key]
    return kept


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MARKS = ("off", "ok", "failed")
_SOURCE_ORDER = ("files", "git", "agents")
_SOURCE_TITLE = {"files": "Files", "git": "Git", "agents": "Agents"}


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _local_dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts)


def _pretty(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]}, {_MONTHS[day.month - 1]} {day.day}, {day.year}"


def _ampm(when: datetime) -> str:
    hour = when.hour
    meridiem = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{when.minute:02d} {meridiem}"


def _stamp(ts: float) -> str:
    when = _local_dt(ts)
    return f"{_pretty(when.date())}, {_ampm(when)}"


def _day_bounds(day: date) -> tuple[float, float]:
    start = datetime.combine(day, datetime.min.time()).timestamp()
    end = datetime.combine(day + timedelta(days=1), datetime.min.time()).timestamp()
    return start, end


def _merge_spans(spans: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    ordered = sorted((start, end) for start, end in spans if end > start)
    merged: List[tuple[float, float]] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        elif end > merged[-1][1]:
            merged[-1] = (merged[-1][0], end)
    return tuple(merged)


def _clip_span(start: float, end: float, day_start: float, day_end: float) -> tuple[float, float] | None:
    clipped_start = day_start if start < day_start else start
    clipped_end = day_end if end > day_end else end
    if clipped_end <= clipped_start:
        return None
    return clipped_start, clipped_end


def _span_text(start: float, end: float, day_end: float) -> str:
    start_text = _ampm(_local_dt(start))
    end_text = "midnight" if end == day_end else _ampm(_local_dt(end))
    return f"{start_text} to {end_text}"


def _sampled_count_phrase(slot_count: int) -> str:
    """"1 half-hour sampled" or "N half-hours sampled". slot_count below 1 is a caller bug."""
    if slot_count < 1:
        raise ValueError("slot_count")
    if slot_count == 1:
        return "1 half-hour sampled"
    return f"{slot_count} half-hours sampled"


def _event_key(event: Mapping[str, Any]) -> tuple | None:
    kind = event.get("type")
    if kind == "git":
        digest = event.get("hash")
        if not isinstance(digest, str) or not digest:
            return None
        return ("git", digest)
    if kind == "file":
        repo = event.get("repo")
        path = event.get("path")
        day = event.get("day")
        slot = event.get("slot")
        if repo is None or path is None or day is None or slot is None:
            return None
        return ("file", repo, path, day, slot)
    if kind == "agent":
        agent = event.get("agent")
        day = event.get("day")
        slot = event.get("slot")
        if agent is None or day is None or slot is None:
            return None
        return ("agent", agent, day, slot)
    return None


def _agent_pairs(raw: Mapping[str, int] | None) -> tuple[tuple[str, int], ...]:
    if not raw:
        return ()
    pairs = [
        (key, value)
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
    ]
    pairs.sort(key=lambda item: item[0])
    return tuple(pairs)


def _blank_state() -> "ScanState":
    return ScanState(
        first_sample_at=None,
        file_cursor=0,
        file_windows=(),
        files_ok_at=None,
        git_ok_at=None,
        agents_ok_at=None,
        last_attempt_at=None,
        last_files=None,
        last_git=None,
        last_agents=None,
        agent_counts=(),
    )


def _forward(previous: float | None, now: float) -> float:
    if previous is None or now >= previous:
        return now
    return previous


def _probe_mark(probe: "Probe") -> Literal["off", "ok", "failed"]:
    if isinstance(probe, ProbeOff):
        return "off"
    if isinstance(probe, ProbeOk):
        return "ok"
    if isinstance(probe, ProbeFailed):
        return "failed"
    raise TypeError(type(probe).__name__)


def _probe_events(probe: "Probe") -> tuple[Mapping[str, Any], ...]:
    if isinstance(probe, (ProbeOk, ProbeFailed)):
        return tuple(probe.events)
    return ()


@dataclass(frozen=True)
class ProbeOff:
    """The source is disabled, or it is enabled and there is nothing to walk."""


@dataclass(frozen=True)
class ProbeOk:
    """Every walked target finished. An empty event tuple is a successful look."""

    events: tuple[Mapping[str, Any], ...] = ()
    agent_counts: Mapping[str, int] | None = None


@dataclass(frozen=True)
class ProbeFailed:
    """At least one walked target did not finish. events are the roots that did."""

    events: tuple[Mapping[str, Any], ...] = ()


Probe = ProbeOff | ProbeOk | ProbeFailed


@dataclass(frozen=True)
class FileWindow:
    """One fully successful file walk, as a half-open unix interval [start, end)."""

    start: float
    end: float

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("file window end must be greater than start")


@dataclass(frozen=True)
class ScanState:
    first_sample_at: float | None
    file_cursor: float
    file_windows: tuple[FileWindow, ...]
    files_ok_at: float | None
    git_ok_at: float | None
    agents_ok_at: float | None
    last_attempt_at: float | None
    last_files: Literal["off", "ok", "failed"] | None
    last_git: Literal["off", "ok", "failed"] | None
    last_agents: Literal["off", "ok", "failed"] | None
    agent_counts: tuple[tuple[str, int], ...]

    def to_json(self) -> dict[str, Any]:
        """state.json object. Omits lastSampleAt and seenGit."""
        payload: dict[str, Any] = {
            "fileCursor": self.file_cursor,
            "fileWindows": [[window.start, window.end] for window in self.file_windows],
            "okAt": {
                "files": self.files_ok_at,
                "git": self.git_ok_at,
                "agents": self.agents_ok_at,
            },
            "agentCounts": {key: value for key, value in self.agent_counts},
        }
        if self.first_sample_at is not None:
            payload = {"firstSampleAt": self.first_sample_at, **payload}
        if (
            self.last_attempt_at is not None
            and self.last_files in _MARKS
            and self.last_git in _MARKS
            and self.last_agents in _MARKS
        ):
            payload["lastAttempt"] = {
                "at": self.last_attempt_at,
                "files": self.last_files,
                "git": self.last_git,
                "agents": self.last_agents,
            }
        return payload


@dataclass(frozen=True)
class ScanPlan:
    """Ledger rows still absent, and the state to rename into place."""

    events_to_append: tuple[Mapping[str, Any], ...]
    state: ScanState


@dataclass(frozen=True)
class DayCoverage:
    day: str
    coverage: Literal["unknown", "gap", "sampled", "git-history-only"]
    observed_slots: int
    observed_slot_indexes: tuple[int, ...]
    slots: int
    slot_indexes: tuple[int, ...]
    commits: int
    files: int
    agents: int
    repos: tuple[str, ...]
    by_slot: dict[str, Any]
    intervals: tuple[tuple[float, float], ...]
    read_at: float | None
    paint: Literal["dim", "pale", "lit"]
    label: str
    headline: str

    def as_heatmap_day(self) -> dict[str, Any]:
        """heatmap.json day. Omits intervals and read_at."""
        return {
            "slots": self.slots,
            "commits": self.commits,
            "files": self.files,
            "agents": self.agents,
            "repos": list(self.repos),
            "coverage": self.coverage,
            "slotIndexes": list(self.slot_indexes),
            "bySlot": self.by_slot,
            "observedSlots": self.observed_slots,
            "paint": self.paint,
            "label": self.label,
            "headline": self.headline,
        }


def process_failed(returncode: int | None, failure: str | None) -> bool:
    """Exit 0 and failure None is success, including empty stdout. Any other result failed."""
    if failure is not None:
        return True
    if returncode is None:
        return True
    return returncode != 0


def combine_file_probes(parts: Sequence[ProbeOk | ProbeFailed]) -> ProbeOk | ProbeFailed:
    """One failed root fails the file probe. Events stay in part order, including successes."""
    if not parts:
        raise ValueError("combine_file_probes requires at least one probe")
    events: List[Mapping[str, Any]] = []
    failed = False
    for part in parts:
        if isinstance(part, ProbeFailed):
            failed = True
        elif not isinstance(part, ProbeOk):
            raise TypeError(type(part).__name__)
        events.extend(part.events)
    if failed:
        return ProbeFailed(events=tuple(events))
    return ProbeOk(events=tuple(events))


def parse_scan_state(raw: Mapping[str, Any] | None) -> ScanState:
    """Read state.json. firstSampleAt and lastSampleAt never become a window or a success clock."""
    if not isinstance(raw, Mapping):
        return _blank_state()

    if _is_num(raw.get("fileCursor")):
        cursor = float(raw["fileCursor"])
    elif _is_num(raw.get("lastSampleAt")):
        cursor = float(raw["lastSampleAt"])
    else:
        cursor = 0
    if cursor < 0:
        cursor = 0

    spans: List[tuple[float, float]] = []
    raw_windows = raw.get("fileWindows")
    if isinstance(raw_windows, list):
        for pair in raw_windows:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            if not _is_num(pair[0]) or not _is_num(pair[1]):
                continue
            spans.append((float(pair[0]), float(pair[1])))
    windows = tuple(FileWindow(start, end) for start, end in _merge_spans(spans))

    first = raw.get("firstSampleAt")
    first_sample_at = float(first) if _is_num(first) and float(first) > 0 else None

    files_ok_at = None
    git_ok_at = None
    agents_ok_at = None
    ok_at = raw.get("okAt")
    if isinstance(ok_at, Mapping):
        if _is_num(ok_at.get("files")):
            files_ok_at = float(ok_at["files"])
        if _is_num(ok_at.get("git")):
            git_ok_at = float(ok_at["git"])
        if _is_num(ok_at.get("agents")):
            agents_ok_at = float(ok_at["agents"])

    last_attempt_at = None
    last_files = None
    last_git = None
    last_agents = None
    attempt = raw.get("lastAttempt")
    if isinstance(attempt, Mapping):
        at = attempt.get("at")
        marks = (attempt.get("files"), attempt.get("git"), attempt.get("agents"))
        if _is_num(at) and all(mark in _MARKS for mark in marks):
            last_attempt_at = float(at)
            last_files, last_git, last_agents = marks

    return ScanState(
        first_sample_at=first_sample_at,
        file_cursor=cursor,
        file_windows=windows,
        files_ok_at=files_ok_at,
        git_ok_at=git_ok_at,
        agents_ok_at=agents_ok_at,
        last_attempt_at=last_attempt_at,
        last_files=last_files,
        last_git=last_git,
        last_agents=last_agents,
        agent_counts=_agent_pairs(raw.get("agentCounts") if isinstance(raw.get("agentCounts"), Mapping) else None),
    )


def plan_scan(
    state: ScanState,
    ledger_events: Sequence[Mapping[str, Any]],
    files: Probe,
    git: Probe,
    agents: Probe,
    now: float,
    midnight: float,
) -> ScanPlan:
    """Next ledger rows and state. The file cursor moves only after a full file success past its since."""
    since = file_since_ts(state.file_cursor, midnight)
    files_mark = _probe_mark(files)
    git_mark = _probe_mark(git)
    agents_mark = _probe_mark(agents)

    seen = set()
    for event in ledger_events:
        if isinstance(event, Mapping):
            key = _event_key(event)
            if key is not None:
                seen.add(key)
    fresh: List[Mapping[str, Any]] = []
    for probe in (files, git, agents):
        for event in _probe_events(probe):
            if not isinstance(event, Mapping):
                continue
            key = _event_key(event)
            if key is None or key in seen:
                continue
            seen.add(key)
            fresh.append(event)

    file_cursor = state.file_cursor
    file_windows = state.file_windows
    files_ok_at = state.files_ok_at
    git_ok_at = state.git_ok_at
    agents_ok_at = state.agents_ok_at
    agent_counts = state.agent_counts

    if files_mark == "ok":
        files_ok_at = _forward(files_ok_at, now)
        if now > since:
            file_windows = tuple(
                FileWindow(start, end)
                for start, end in _merge_spans([*[(w.start, w.end) for w in file_windows], (since, now)])
            )
            file_cursor = now
    if git_mark == "ok":
        git_ok_at = _forward(git_ok_at, now)
    if agents_mark == "ok" and isinstance(agents, ProbeOk):
        agents_ok_at = _forward(agents_ok_at, now)
        agent_counts = _agent_pairs(agents.agent_counts)
    elif agents_mark == "off":
        agent_counts = ()

    first_sample_at = state.first_sample_at
    if first_sample_at is None and "ok" in (files_mark, git_mark, agents_mark):
        first_sample_at = now

    if state.last_attempt_at is None or now >= state.last_attempt_at:
        last_attempt_at: float | None = now
        last_files: Literal["off", "ok", "failed"] | None = files_mark
        last_git: Literal["off", "ok", "failed"] | None = git_mark
        last_agents: Literal["off", "ok", "failed"] | None = agents_mark
    else:
        last_attempt_at = state.last_attempt_at
        last_files = state.last_files
        last_git = state.last_git
        last_agents = state.last_agents

    return ScanPlan(
        events_to_append=tuple(fresh),
        state=ScanState(
            first_sample_at=first_sample_at,
            file_cursor=file_cursor,
            file_windows=file_windows,
            files_ok_at=files_ok_at,
            git_ok_at=git_ok_at,
            agents_ok_at=agents_ok_at,
            last_attempt_at=last_attempt_at,
            last_files=last_files,
            last_git=last_git,
            last_agents=last_agents,
            agent_counts=agent_counts,
        ),
    )


def _empty_tally() -> Dict[str, Any]:
    return {
        "slots": set(),
        "obs": set(),
        "git_slots": set(),
        "commits": 0,
        "files": set(),
        "agents": 0,
        "repos": set(),
        "by_slot": {},
    }


def _tally_events(events: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    days: Dict[str, Dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, Mapping):
            continue
        day = event.get("day")
        if not isinstance(day, str) or not day:
            continue
        bucket = days.setdefault(day, _empty_tally())
        slot = event.get("slot")
        if isinstance(slot, int) and not isinstance(slot, bool):
            bucket["slots"].add(slot)
            info = bucket["by_slot"].setdefault(slot, {"git": 0, "file": 0, "repos": set()})
            kind = event.get("type")
            if kind == "git":
                bucket["git_slots"].add(slot)
                bucket["commits"] += 1
                info["git"] += 1
            elif kind == "file":
                bucket["obs"].add(slot)
                path = event.get("path") or ""
                if path:
                    bucket["files"].add(f"{event.get('repo') or ''}:{path}")
                info["file"] += 1
            elif kind == "agent":
                bucket["obs"].add(slot)
                bucket["agents"] += 1
            repo = event.get("repo")
            if isinstance(repo, str) and repo:
                info["repos"].add(repo)
        repo = event.get("repo")
        if isinstance(repo, str) and repo:
            bucket["repos"].add(repo)
    return days


def _first_local_day(state: ScanState) -> date | None:
    if state.first_sample_at is not None:
        return _local_dt(state.first_sample_at).date()
    if state.file_windows:
        return _local_dt(min(window.start for window in state.file_windows)).date()
    return None


def _day_label(
    pretty: str,
    coverage: str,
    observed: int,
    intervals: tuple[tuple[float, float], ...],
    read_at: float | None,
    day_start: float,
    day_end: float,
) -> str:
    if coverage == "unknown":
        return f"{pretty} · not monitored yet"
    if coverage == "gap":
        return f"{pretty} · no successful scan"
    if coverage == "git-history-only":
        return f"{pretty} · git history only, may not have happened on this PC"
    later = read_at is not None and read_at > day_end
    if observed > 0:
        label = f"{pretty} · {_sampled_count_phrase(observed)}"
        if later:
            label += f" · read {_stamp(read_at)}"
        return label
    full_day = (
        len(intervals) == 1
        and intervals[0][0] == day_start
        and intervals[0][1] == day_end
        and later
    )
    if full_day:
        return f"{pretty} · no file changes still on disk · sampled {_stamp(read_at)}"
    noun = "windows" if len(intervals) > 1 else "window"
    spans = ", ".join(_span_text(start, end, day_end) for start, end in intervals)
    label = f"{pretty} · no file changes in the sampled {noun} · {spans}"
    if intervals and intervals[0][0] > day_start:
        label += f" · before {_ampm(_local_dt(intervals[0][0]))} was not sampled"
    if later:
        label += f" · read {_stamp(read_at)}"
    return label


def _day_headline(coverage: str, observed: int) -> str:
    if coverage == "unknown":
        return "Not monitored yet"
    if coverage == "gap":
        return "No successful scan today"
    if coverage == "git-history-only":
        return "Git history only today"
    if observed <= 0:
        return "No file changes in the sampled window today"
    if observed == 1:
        return "1 half-hour sampled on this machine today"
    return f"{observed} half-hours sampled on this machine today"


def _paint(coverage: str, observed: int) -> Literal["dim", "pale", "lit"]:
    if coverage == "git-history-only":
        return "pale"
    if coverage == "sampled" and observed > 0:
        return "lit"
    return "dim"


def cover_days(
    events: Sequence[Mapping[str, Any]],
    state: ScanState,
    start: date,
    end: date,
) -> dict[str, DayCoverage]:
    """Every local day from start through end. Only end gets a headline. Bounds are local midnights."""
    tallies = _tally_events(events)
    first_day = _first_local_day(state)
    covered: dict[str, DayCoverage] = {}
    day = start
    while day <= end:
        iso = day.isoformat()
        day_start, day_end = _day_bounds(day)
        hits = [window for window in state.file_windows if window.start < day_end and window.end > day_start]
        read_at = max((window.end for window in hits), default=None)
        clipped = []
        for window in hits:
            piece = _clip_span(window.start, window.end, day_start, day_end)
            if piece is not None:
                clipped.append(piece)
        intervals = _merge_spans(clipped)
        bucket = tallies.get(iso) or _empty_tally()
        observed_indexes = tuple(sorted(bucket["obs"]))
        slot_indexes = tuple(sorted(bucket["slots"]))
        observed = len(observed_indexes)
        if observed:
            coverage = "sampled"
        elif bucket["git_slots"]:
            coverage = "git-history-only"
        elif intervals:
            coverage = "sampled"
        elif first_day is None or day < first_day:
            coverage = "unknown"
        else:
            coverage = "gap"
        by_slot = {
            str(index): {
                "git": info["git"],
                "file": info["file"],
                "repos": sorted(info["repos"]),
            }
            for index, info in sorted(bucket["by_slot"].items())
        }
        pretty = _pretty(day)
        covered[iso] = DayCoverage(
            day=iso,
            coverage=coverage,
            observed_slots=observed,
            observed_slot_indexes=observed_indexes,
            slots=len(slot_indexes),
            slot_indexes=slot_indexes,
            commits=bucket["commits"],
            files=len(bucket["files"]),
            agents=bucket["agents"],
            repos=tuple(sorted(bucket["repos"])),
            by_slot=by_slot,
            intervals=intervals,
            read_at=read_at,
            paint=_paint(coverage, observed),
            label=_day_label(pretty, coverage, observed, intervals, read_at, day_start, day_end),
            headline=_day_headline(coverage, observed) if day == end else "",
        )
        day += timedelta(days=1)
    return covered


def scan_status_text(state: ScanState, timer_enabled: bool) -> str:
    """Settings sentence. The timer clause says enabled or off, and never a cadence."""
    timer = "Timer enabled." if timer_enabled else "Timer off."
    marks = (state.last_files, state.last_git, state.last_agents)
    if state.last_attempt_at is None or any(mark not in _MARKS for mark in marks):
        return f"No successful scan yet. {timer}"
    if all(mark == "off" for mark in marks):
        return f"No successful scan yet. {timer}"

    stamp = _stamp(state.last_attempt_at)
    clocks = {
        "files": state.files_ok_at,
        "git": state.git_ok_at,
        "agents": state.agents_ok_at,
    }
    enabled = [(name, mark) for name, mark in zip(_SOURCE_ORDER, marks) if mark != "off"]

    def clock_sentences(names: Sequence[str]) -> List[str]:
        lines = []
        for name in names:
            ok_at = clocks[name]
            if ok_at is not None:
                lines.append(f"{_SOURCE_TITLE[name]} last ok {_stamp(ok_at)}.")
            elif name == "files":
                lines.append("No successful file scan yet.")
        return lines

    if all(mark == "ok" for _, mark in enabled):
        return f"Last scan {stamp}. {timer}"

    failed = [name for name, mark in enabled if mark == "failed"]
    if all(mark == "failed" for _, mark in enabled):
        pieces = [f"Last scan failed {stamp}."]
    else:
        parts = ", ".join(f"{name} {mark}" for name, mark in enabled)
        pieces = [f"Last scan {stamp}, partial, {parts}."]
    pieces.extend(clock_sentences(failed))
    pieces.append(timer)
    return " ".join(pieces)


def week_clause(slot_count: int) -> str:
    """Opening clause of the review sentence. slot_count is observed slots, not hours."""
    if slot_count == 0:
        return "No half-hours sampled this week on this Omarchy box"
    if slot_count == 1:
        return "1 half-hour sampled this week on this Omarchy box"
    return f"{slot_count} half-hours sampled this week on this Omarchy box"
