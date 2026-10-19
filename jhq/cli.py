"""jhq: the Job Hunt HQ command line. Claude runs these for you; you rarely need to.

    jhq init --data-dir PATH [--timezone Area/City]   create your data folder
    jhq doctor                                        check the install
    jhq where                                         print every important path
    jhq build spec.json [--overwrite]                 build + check an application package
    jhq ats resume.pdf --keywords kw.json             measured ATS check
    jhq md2docx in.md out.docx                        markdown -> Word (prep packs, plans)
    jhq tracker ...                                   the application tracker (see jhq tracker -h)
    jhq skillgap [--print]                            skill-gap heatmap data
    jhq radar run|sync|stats|learn                    daily radar, Applied sync, run health, learned rules
    jhq leads ...                                     the Jobs-tab lead store
    jhq companies ...                                 the radar's company list
    jhq jd <url>                                      read a full job posting
    jhq dashboard [--open] [--autostart on|off]       the local dashboard
    jhq demo                                          try the dashboard with fictional data
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from . import __version__, config


def cmd_init(argv):
    ap = argparse.ArgumentParser(prog="jhq init")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--timezone", help="IANA name, e.g. America/Chicago (default: this computer's)")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    data = Path(a.data_dir).expanduser().resolve()
    app = config.APP_DIR.resolve()
    if data == app or app in data.parents:
        raise SystemExit("Your data folder can't be inside the Job Hunt HQ code folder: it could end up "
                         "on GitHub by accident. Pick a folder like Documents/Job Hunt.")
    if a.timezone:
        from zoneinfo import ZoneInfo
        try:
            ZoneInfo(a.timezone)
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"Unknown timezone '{a.timezone}' (use names like America/Toronto)") from e
    paths = config.Paths(data)
    for d in (paths.profile_dir, paths.applications, paths.tracker_dir, paths.radar, paths.radar_state,
              paths.skillgap_dir):
        d.mkdir(parents=True, exist_ok=True)
    copied = []
    pairs = [(config.TEMPLATES / "profile" / n, paths.profile_dir / n)
             for n in ("profile.json", "facts.md", "rules.md", "star-stories.md", "skill_taxonomy.json")]
    pairs += [(config.TEMPLATES / "radar" / n, paths.radar / n) for n in ("preferences.json", "companies.csv")]
    for src, dst in pairs:
        if not dst.exists():
            shutil.copy2(src, dst)
            copied.append(str(dst))
    from . import tracker
    tracker.init(paths)
    cfg = config.load_config()
    cfg.update(data_dir=str(data), app_dir=str(app), python=sys.executable, dashboard_port=a.port,
               version=__version__)
    if a.timezone:
        cfg["timezone"] = a.timezone
    config.save_config(cfg)
    print(json.dumps({"data_dir": str(data), "config": str(config.config_path()), "created": copied,
                      "tracker": str(paths.tracker)}, indent=2))


def cmd_where(_argv):
    cfg = config.load_config()
    out = {"config": str(config.config_path()), **cfg}
    try:
        p = config.Paths()
        out.update({k: str(v) for k, v in vars(p).items()})
    except SystemExit as e:
        out["error"] = str(e)
    print(json.dumps(out, indent=2))


def cmd_doctor(_argv):
    ok = True

    def line(good, label, detail=""):
        nonlocal ok
        ok &= bool(good) or good is None
        mark = "OK " if good else ("-- " if good is None else "!! ")
        print(f"{mark} {label}{(': ' + detail) if detail else ''}")

    line(sys.version_info >= (3, 9), "Python", platform.python_version())
    for mod in ("docx", "openpyxl", "pymupdf", "pypdf", "requests"):
        try:
            __import__(mod)
            line(True, f"package {mod}")
        except ImportError:
            line(False, f"package {mod}", "missing: rerun install.py")
    from .pdf_export import available
    pdf = available()
    line(bool(pdf), "PDF export", ", ".join(pdf) or "install LibreOffice (free) or Microsoft Word")
    cfg = config.load_config()
    line(True if cfg.get("data_dir") else None, "data folder",
         cfg.get("data_dir") or "not set up yet: in Claude Code say \"set up Job Hunt HQ\"")
    if cfg.get("data_dir"):
        try:
            p = config.Paths()
            prof = config.read_json(p.profile, {}) or {}
            filled = prof.get("name") and prof.get("name") != "Your Name" and prof.get("email")
            line(bool(filled), "profile", "complete" if filled else f"fill in {p.profile} (the setup does this)")
            line(p.facts.exists() and p.facts.stat().st_size > 400, "facts.md (your truth source)",
                 str(p.facts))
            base = prof.get("base_resume")
            line(bool(base) and (p.root / base).exists() if base else None, "base resume", base or "not added yet")
            line(p.tracker.exists(), "tracker", str(p.tracker))
            prefs = config.read_json(p.prefs, {}) or {}
            areas = [m for a in prefs.get("areas", []) for m in a.get("match", [])]
            set_up = bool(prefs.get("country")) and areas and areas != ["your city"]
            line(True if set_up else None, "radar preferences",
                 "set" if set_up else "country/areas not set yet (setup step 6)")
            from .radar.companies import load
            n = len(load(p))
            line(True if n else None, "radar companies", f"{n} listed" if n else "none yet (optional)")
        except SystemExit as e:
            line(False, "data folder", str(e))
    skills = Path.home() / ".claude" / "skills"
    have = [s for s in ("job-hunt", "job-hunt-setup", "job-radar") if (skills / s / "SKILL.md").exists()]
    line(len(have) == 3, "Claude skills", ", ".join(have) or f"not installed in {skills}")
    print("\nAll good." if ok else "\nSome checks need attention (see !! above).")
    return 0 if ok else 1


# ---------------------------------------------------------------- autostart
def _pythonw():
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.exists() else exe


def desktop_escape(path: str) -> str:
    """Quote a path for a .desktop Exec line (inside double quotes)."""
    return path.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")


def autostart(state: str, dry=False) -> str:
    """Start the dashboard when you log in (on) or stop doing that (off)."""
    if sys.platform == "win32":
        startup = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
        target = startup / "Job Hunt HQ dashboard.vbs"
        body = ('Set sh = CreateObject("WScript.Shell")\r\n'
                f'sh.Run """{_pythonw()}"" -m jhq dashboard --quiet", 0, False\r\n')
    elif sys.platform == "darwin":
        target = Path.home() / "Library/LaunchAgents/com.jobhunthq.dashboard.plist"
        body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0"><dict>\n'
                '<key>Label</key><string>com.jobhunthq.dashboard</string>\n'
                f'<key>ProgramArguments</key><array><string>{xml_escape(sys.executable)}</string><string>-m</string>'
                '<string>jhq</string><string>dashboard</string><string>--quiet</string></array>\n'
                '<key>RunAtLoad</key><true/>\n</dict></plist>\n')
    else:
        target = Path.home() / ".config/autostart/job-hunt-hq.desktop"
        body = ("[Desktop Entry]\nType=Application\nName=Job Hunt HQ dashboard\n"
                f"Exec=\"{desktop_escape(sys.executable)}\" -m jhq dashboard --quiet\nX-GNOME-Autostart-enabled=true\n")
    if dry:
        return f"{target}\n---\n{body}"
    if state == "on":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        if sys.platform == "darwin":
            subprocess.run(["launchctl", "load", str(target)], capture_output=True)
        return f"Dashboard will start when you log in ({target})."
    if target.exists():
        if sys.platform == "darwin":
            subprocess.run(["launchctl", "unload", str(target)], capture_output=True)
        target.unlink()
        return f"Removed {target}."
    return "Autostart was not on."


def cmd_dashboard(argv):
    if "--autostart" in argv:
        i = argv.index("--autostart")
        state = argv[i + 1] if i + 1 < len(argv) else ""
        if state not in ("on", "off", "show"):
            raise SystemExit("Use --autostart on, off or show")
        print(autostart(state, dry=state == "show"))
        return
    from .dashboard import server
    server.main(argv)


def main(argv=None):
    config.utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv[0] in ("-V", "--version", "version"):
        print(__version__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "init":
        return cmd_init(rest)
    if cmd == "where":
        return cmd_where(rest)
    if cmd == "doctor":
        return cmd_doctor(rest)
    if cmd == "dashboard":
        return cmd_dashboard(rest)
    if cmd == "radar":
        sub = rest[0] if rest else ""
        if sub == "run":
            from .radar import run
            return run.main(rest[1:])
        if sub == "sync":
            from .radar import sync
            return sync.main(rest[1:])
        if sub == "stats":
            from .radar import stats
            return stats.main(rest[1:])
        if sub == "learn":
            from .radar import learn
            return learn.main(rest[1:])
        raise SystemExit("Use: jhq radar run | sync | stats | learn")
    modules = {"demo": "demo", "build": "build_package", "ats": "ats_check", "md2docx": "md_to_docx", "tracker": "tracker",
               "skillgap": "skill_gap", "leads": "radar.leads", "companies": "radar.companies", "jd": "radar.jd"}
    if cmd not in modules:
        raise SystemExit(f"Unknown command '{cmd}'. Run `jhq help`.")
    import importlib
    mod = importlib.import_module(f".{modules[cmd]}", __package__)
    return mod.main(rest)


if __name__ == "__main__":
    sys.exit(main() or 0)
