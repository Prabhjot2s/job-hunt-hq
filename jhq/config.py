"""Where everything lives.

Two places, kept apart on purpose:
- The app (this repo): code, skills, templates. Safe to update with `git pull`.
- Your data folder (chosen during setup): profile, resume, applications, tracker, job leads.
  It is never inside the repo, so your data can't be committed by accident.

`~/.job-hunt-hq/config.json` links the two. Set JHQ_HOME to use another config folder (tests do).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES = APP_DIR / "templates"


def home() -> Path:
    return Path(os.environ.get("JHQ_HOME") or Path.home() / ".job-hunt-hq")


def config_path() -> Path:
    return home() / "config.json"


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, data, indent=1):
    """Atomic write: a crash mid-write never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=indent, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def load_config() -> dict:
    return read_json(config_path(), {}) or {}


def save_config(cfg: dict):
    write_json(config_path(), cfg, indent=2)


class NotSetUp(SystemExit):
    pass


def data_dir() -> Path:
    d = load_config().get("data_dir")
    if not d:
        raise NotSetUp("Job Hunt HQ isn't set up yet: no data folder in "
                       f"{config_path()}. Run the setup (ask Claude: 'set up Job Hunt HQ').")
    p = Path(d).expanduser()
    if not p.exists():
        raise NotSetUp(f"Data folder not found: {p}. Is the drive connected? Stop and tell the user.")
    return p


class Paths:
    """Every file inside the data folder."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else data_dir()
        self.profile_dir = self.root / "profile"
        self.profile = self.profile_dir / "profile.json"
        self.facts = self.profile_dir / "facts.md"
        self.rules = self.profile_dir / "rules.md"
        self.stories = self.profile_dir / "star-stories.md"
        self.taxonomy = self.profile_dir / "skill_taxonomy.json"
        self.applications = self.root / "applications"
        self.tracker_dir = self.root / "tracker"
        self.tracker = self.tracker_dir / "applications.xlsx"
        self.backups = self.tracker_dir / "backups"
        self.radar = self.root / "radar"
        self.prefs = self.radar / "preferences.json"
        self.companies = self.radar / "companies.csv"
        self.leads = self.radar / "leads.json"
        self.lead_status = self.radar / "lead_status.json"
        self.radar_state = self.radar / "state"
        self.seen = self.radar_state / "seen.json"
        self.synced = self.radar_state / "synced.json"
        self.discovery = self.radar_state / "discovery.json"
        self.runs = self.radar / "runs"
        self.review = self.radar / "weekly_review.json"
        self.skillgap_dir = self.root / "skill-gap"
        self.skillgap = self.skillgap_dir / "skill_gap.json"


def profile(paths: Paths | None = None) -> dict:
    p = paths or Paths()
    data = read_json(p.profile)
    if not data:
        raise NotSetUp(f"No profile at {p.profile}. Run the setup first.")
    return data


def prefs(paths: Paths | None = None) -> dict:
    p = paths or Paths()
    return read_json(p.prefs, {}) or {}


def timezone():
    """The user's timezone from config, else the computer's."""
    name = load_config().get("timezone")
    if name:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name)
        except Exception:  # noqa: BLE001  (bad name or no tz database)
            pass
    return dt.datetime.now().astimezone().tzinfo


def today() -> dt.date:
    return dt.datetime.now(timezone()).date()


def parse_day(v) -> dt.date | None:
    """'today', 'yesterday', 'YYYY-MM-DD', a date or a datetime."""
    if v in (None, ""):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v).strip().lower()
    if s == "today":
        return today()
    if s == "yesterday":
        return today() - dt.timedelta(days=1)
    return dt.date.fromisoformat(s[:10])


_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(text: str, limit: int = 90) -> str:
    """A folder/file name that works on Windows, macOS and Linux."""
    s = _UNSAFE.sub("-", str(text)).strip().strip(".")
    s = re.sub(r"\s+", " ", s)
    return s[:limit].rstrip(" .-") or "untitled"


def file_stub(name: str) -> str:
    """'Alex Sample' -> 'Alex_Sample' for resume file names."""
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "Resume"


def utf8_console():
    for s in (sys.stdout, sys.stderr):
        getattr(s, "reconfigure", lambda **k: None)(encoding="utf-8")
