"""Local Contributions dashboard plugin backend.

Mounted at /api/plugins/local-contrib/ by Hermes.
Scans configured git roots on this machine and returns a GitHub-style
per-day commit heatmap (authored by the local git user by default).
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    from hermes_constants import get_hermes_home
except ImportError:
    def get_hermes_home() -> Path:  # type: ignore[misc]
        val = (os.environ.get("HERMES_HOME") or "").strip()
        return Path(val) if val else Path.home() / ".hermes"

try:
    from fastapi import APIRouter, Query
except Exception:  # Allows import without dashboard dependencies.
    class APIRouter:  # type: ignore
        def get(self, *_args, **_kwargs):
            return lambda fn: fn

        def post(self, *_args, **_kwargs):
            return lambda fn: fn

    def Query(default: Any = None, **_kwargs: Any) -> Any:  # type: ignore
        return default

router = APIRouter()

SNAPSHOT_TTL_SECONDS = 90
GIT_TIMEOUT = 12
MAX_DEPTH = 6
MAX_COMMITS_PER_DAY = 80
DEFAULT_ROOTS = ["~/Projects", "~/Documents"]
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "dist",
    "build",
    ".cache",
    ".tox",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "vendor",
    ".next",
    ".turbo",
    "coverage",
}

_SCAN_LOCK = threading.Lock()
_SNAPSHOT: Optional[Dict[str, Any]] = None
_SNAPSHOT_AT = 0.0

SETTINGS_PATH = get_hermes_home() / "state" / "local-contrib.json"


def _load_settings() -> Dict[str, Any]:
    defaults = {
        "roots": list(DEFAULT_ROOTS),
        "author": "mine",  # mine | all
        "includeMerges": False,
    }
    try:
        if SETTINGS_PATH.is_file():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(data)
    except Exception:
        pass
    if not isinstance(defaults.get("roots"), list) or not defaults["roots"]:
        defaults["roots"] = list(DEFAULT_ROOTS)
    if defaults.get("author") not in ("mine", "all"):
        defaults["author"] = "mine"
    return defaults


def _save_settings(settings: Dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def _git(repo: Path, args: List[str], timeout: int = GIT_TIMEOUT) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def _git_config(repo: Optional[Path], key: str) -> str:
    try:
        cmd = ["git", "config", "--global", "--get", key] if repo is None else [
            "git", "-C", str(repo), "config", "--get", key
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=4, check=False)
        return (result.stdout or "").strip()
    except Exception:
        return ""


def _expand_root(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def discover_repos(roots: Iterable[str], max_depth: int = MAX_DEPTH) -> List[Path]:
    found: List[Path] = []
    seen: Set[str] = set()
    for raw in roots:
        try:
            root = _expand_root(raw)
        except Exception:
            continue
        if not root.is_dir():
            continue
        for dirpath, dirnames, _files in os.walk(root, followlinks=False):
            rel = Path(dirpath)
            try:
                depth = len(rel.relative_to(root).parts)
            except ValueError:
                dirnames[:] = []
                continue
            if depth > max_depth:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            git_entry = Path(dirpath) / ".git"
            if git_entry.exists():
                repo = Path(dirpath)
                key = str(repo)
                if key not in seen:
                    seen.add(key)
                    found.append(repo)
                dirnames[:] = []
    found.sort(key=lambda p: str(p).lower())
    return found


def _collect_identities(repos: List[Path]) -> Tuple[Set[str], Set[str]]:
    emails: Set[str] = set()
    names: Set[str] = set()
    for source in (None, *repos):
        email = _git_config(source, "user.email").lower()
        name = _git_config(source, "user.name").lower()
        if email:
            emails.add(email)
        if name:
            names.add(name)
    return emails, names


def _is_mine(an: str, ae: str, emails: Set[str], names: Set[str]) -> bool:
    ae_l = ae.strip().lower()
    an_l = an.strip().lower()
    if ae_l and ae_l in emails:
        return True
    if an_l and an_l in names:
        return True
    return False


def _parse_numstat_block(text: str) -> List[Dict[str, Any]]:
    commits: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("COMMIT\t"):
            if current is not None:
                commits.append(current)
            parts = line.split("\t", 5)
            if len(parts) < 6:
                current = None
                continue
            _marker, full_hash, day, author, email, subject = parts
            current = {
                "hash": full_hash[:12],
                "fullHash": full_hash,
                "date": day,
                "author": author,
                "email": email,
                "subject": subject.strip() or "(no subject)",
                "additions": 0,
                "deletions": 0,
            }
            continue
        if current is None or not line:
            continue
        bits = line.split("\t", 2)
        if len(bits) < 2:
            continue
        add_s, del_s = bits[0], bits[1]
        if add_s != "-":
            try:
                current["additions"] += int(add_s)
            except ValueError:
                pass
        if del_s != "-":
            try:
                current["deletions"] += int(del_s)
            except ValueError:
                pass
    if current is not None:
        commits.append(current)
    return commits


def _scan_repo(repo: Path, since: str, include_merges: bool) -> List[Dict[str, Any]]:
    args = [
        "log",
        "--all",
        "--since",
        since,
        "--pretty=format:COMMIT\t%H\t%ad\t%an\t%ae\t%s",
        "--date=short",
        "--numstat",
    ]
    if not include_merges:
        args.append("--no-merges")
    try:
        text = _git(repo, args, timeout=GIT_TIMEOUT)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []
    if not text.strip():
        return []
    commits = _parse_numstat_block(text)
    label = repo.name
    try:
        home = str(Path.home())
        rel = str(repo)
        if rel.startswith(home + os.sep):
            label = "~" + rel[len(home) :]
        else:
            label = rel
    except Exception:
        pass
    for commit in commits:
        commit["repo"] = label
        commit["repoPath"] = str(repo)
    return commits


def _empty_snapshot(settings: Dict[str, Any], repos: List[Path], error: Optional[str] = None) -> Dict[str, Any]:
    today = date.today().isoformat()
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "authorMode": settings.get("author", "mine"),
        "authors": [],
        "roots": settings.get("roots", DEFAULT_ROOTS),
        "repos": [{"path": str(p), "name": p.name, "commits": 0} for p in repos],
        "years": [date.today().year],
        "days": {},
        "commitsByDay": {},
        "total": 0,
        "today": {"date": today, "commits": 0},
        "error": error,
    }


def build_snapshot(force: bool = False) -> Dict[str, Any]:
    global _SNAPSHOT, _SNAPSHOT_AT
    now = time.time()
    with _SCAN_LOCK:
        if not force and _SNAPSHOT is not None and (now - _SNAPSHOT_AT) < SNAPSHOT_TTL_SECONDS:
            return _SNAPSHOT
        settings = _load_settings()
        try:
            repos = discover_repos(settings.get("roots") or DEFAULT_ROOTS)
        except Exception as exc:
            snap = _empty_snapshot(settings, [], error=str(exc))
            _SNAPSHOT, _SNAPSHOT_AT = snap, now
            return snap

        since = (date.today() - timedelta(days=366 * 4)).isoformat()
        emails, names = _collect_identities(repos)
        author_mode = settings.get("author", "mine")
        include_merges = bool(settings.get("includeMerges"))

        all_commits: List[Dict[str, Any]] = []
        for repo in repos:
            all_commits.extend(_scan_repo(repo, since, include_merges))

        if author_mode == "mine" and (emails or names):
            all_commits = [c for c in all_commits if _is_mine(c["author"], c["email"], emails, names)]
            for commit in all_commits:
                ae = (commit.get("email") or "").strip().lower()
                if ae:
                    emails.add(ae)

        days: Dict[str, Dict[str, Any]] = {}
        commits_by_day: Dict[str, List[Dict[str, Any]]] = {}
        repo_counts: Dict[str, int] = {}
        years: Set[int] = set()
        seen_hashes: Set[str] = set()

        for commit in all_commits:
            key = f"{commit['fullHash']}:{commit.get('repoPath', '')}"
            if key in seen_hashes:
                continue
            seen_hashes.add(key)
            day = commit["date"]
            if len(day) < 10:
                continue
            try:
                years.add(int(day[:4]))
            except ValueError:
                continue
            bucket = days.setdefault(
                day,
                {"commits": 0, "additions": 0, "deletions": 0, "repos": []},
            )
            bucket["commits"] += 1
            bucket["additions"] += int(commit.get("additions") or 0)
            bucket["deletions"] += int(commit.get("deletions") or 0)
            repo_label = commit.get("repo") or ""
            repos_list: List[str] = bucket["repos"]
            if repo_label and repo_label not in repos_list:
                repos_list.append(repo_label)
            repo_counts[repo_label] = repo_counts.get(repo_label, 0) + 1
            day_list = commits_by_day.setdefault(day, [])
            if len(day_list) < MAX_COMMITS_PER_DAY:
                day_list.append(
                    {
                        "hash": commit["hash"],
                        "subject": commit["subject"],
                        "repo": repo_label,
                        "additions": commit.get("additions") or 0,
                        "deletions": commit.get("deletions") or 0,
                        "author": commit["author"],
                    }
                )

        today = date.today().isoformat()
        years.add(date.today().year)
        snap = {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "authorMode": author_mode,
            "authors": sorted(emails),
            "roots": settings.get("roots", DEFAULT_ROOTS),
            "repos": [
                {"path": str(p), "name": p.name, "commits": repo_counts.get(_repo_label(p), 0)}
                for p in repos
            ],
            "years": sorted(years, reverse=True),
            "days": days,
            "commitsByDay": commits_by_day,
            "total": sum(v["commits"] for v in days.values()),
            "today": {"date": today, "commits": (days.get(today) or {}).get("commits", 0)},
            "error": None,
        }
        # Fill repo commit counts using labels produced in _scan_repo.
        label_counts = repo_counts
        for entry in snap["repos"]:
            path = Path(entry["path"])
            entry["commits"] = label_counts.get(_repo_label(path), 0)

        _SNAPSHOT, _SNAPSHOT_AT = snap, now
        return snap


def _repo_label(repo: Path) -> str:
    try:
        home = str(Path.home())
        rel = str(repo)
        if rel.startswith(home + os.sep):
            return "~" + rel[len(home) :]
        return rel
    except Exception:
        return repo.name


def _public_heatmap(snap: Dict[str, Any], year: Optional[int]) -> Dict[str, Any]:
    today = date.today()
    if year is None:
        start = today - timedelta(days=365)
        end = today
        title_mode = "rolling"
    else:
        start = date(year, 1, 1)
        end = date(year, 12, 31) if year != today.year else today
        title_mode = "year"

    days_out: Dict[str, Any] = {}
    total = 0
    raw_days: Dict[str, Any] = snap.get("days") or {}
    cursor = start
    while cursor <= end:
        iso = cursor.isoformat()
        cell = raw_days.get(iso)
        if cell:
            days_out[iso] = {
                "commits": cell["commits"],
                "additions": cell["additions"],
                "deletions": cell["deletions"],
                "repos": cell["repos"],
            }
            total += cell["commits"]
        cursor += timedelta(days=1)

    return {
        "generatedAt": snap.get("generatedAt"),
        "authorMode": snap.get("authorMode"),
        "authors": snap.get("authors") or [],
        "roots": snap.get("roots") or [],
        "repos": snap.get("repos") or [],
        "years": snap.get("years") or [today.year],
        "year": year,
        "mode": title_mode,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "days": days_out,
        "total": total,
        "today": snap.get("today"),
        "error": snap.get("error"),
    }


@router.get("/heatmap")
async def heatmap(
    year: Optional[int] = Query(default=None),
    refresh: bool = Query(default=False),
):
    snap = build_snapshot(force=refresh)
    return _public_heatmap(snap, year)


@router.get("/day")
async def day_detail(date: str = Query(...), refresh: bool = Query(default=False)):
    snap = build_snapshot(force=refresh)
    commits = (snap.get("commitsByDay") or {}).get(date) or []
    cell = (snap.get("days") or {}).get(date) or {
        "commits": 0,
        "additions": 0,
        "deletions": 0,
        "repos": [],
    }
    return {"date": date, **cell, "entries": commits}


@router.get("/settings")
async def get_settings():
    return _load_settings()


@router.post("/settings")
async def post_settings(body: dict):
    current = _load_settings()
    if isinstance(body, dict):
        if "roots" in body and isinstance(body["roots"], list):
            current["roots"] = [str(x) for x in body["roots"] if str(x).strip()]
        if body.get("author") in ("mine", "all"):
            current["author"] = body["author"]
        if "includeMerges" in body:
            current["includeMerges"] = bool(body["includeMerges"])
        _save_settings(current)
    global _SNAPSHOT_AT
    _SNAPSHOT_AT = 0
    snap = build_snapshot(force=True)
    return {"ok": True, "settings": current, "repos": len(snap.get("repos") or [])}
