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


BULK_CHECKOUT = 15


def drop_bulk_checkout(events: Sequence[Dict[str, Any]], threshold: int = BULK_CHECKOUT) -> List[Dict[str, Any]]:
    """Drop file bursts in a slot with no commit — likely clone/pull, not typing."""
    git_keys = set()
    files_by: Dict[tuple, List[Dict[str, Any]]] = {}
    others: List[Dict[str, Any]] = []
    for event in events:
        kind = event.get("type")
        key = (event.get("day"), event.get("slot"), event.get("repo"))
        if kind == "git":
            git_keys.add(key)
            others.append(event)
        elif kind == "file":
            files_by.setdefault(key, []).append(event)
        else:
            others.append(event)
    kept = list(others)
    for key, files in files_by.items():
        if key not in git_keys and len(files) >= threshold:
            continue
        kept.extend(files)
    return kept
