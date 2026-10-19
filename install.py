"""Install Job Hunt HQ for Claude Code (Windows, macOS, Linux).

    python install.py              # first install, or update after `git pull`
    python install.py --check      # only report what would happen
    python install.py --remove     # remove the Claude skills (your data folder is never touched)

What it does:
  1. Makes a private Python environment in .venv/ (nothing installed system-wide).
  2. Installs the dependencies listed in requirements.txt into it.
  3. Copies the three Claude skills into ~/.claude/skills/ (job-hunt, job-hunt-setup, job-radar),
     filling in the command Claude should use to run the tools on this computer.
Your job-search data lives in a separate folder you choose during setup, never in this repo.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
SKILLS_SRC = ROOT / "skills"
SKILLS_DST = Path.home() / ".claude" / "skills"
SKILLS = ("job-hunt", "job-hunt-setup", "job-radar")
JHQ_HOME = Path(os.environ.get("JHQ_HOME") or Path.home() / ".job-hunt-hq")


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def command() -> str:
    """How Claude should call the tools; forward slashes work in Git Bash, zsh and bash."""
    return f'"{venv_python().as_posix()}" -m jhq'


def step(msg):
    print(f"\n==> {msg}")


def make_venv():
    if venv_python().exists():
        print(f"    using existing {VENV}")
        return
    venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
    print(f"    created {VENV}")


def install_packages():
    py = str(venv_python())
    subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", "pip"], check=False)
    subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r",
                    str(ROOT / "requirements.txt")], check=True)
    subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "-q", "--no-deps", "-e", str(ROOT)],
                   check=True)
    print("    packages installed")


def install_skills():
    SKILLS_DST.mkdir(parents=True, exist_ok=True)
    cmd = command()
    for name in SKILLS:
        src, dst = SKILLS_SRC / name, SKILLS_DST / name
        if dst.exists():
            marker = dst / ".job-hunt-hq"
            if not marker.exists():
                bk = dst.with_name(f"{name}.backup-{dt.datetime.now():%Y%m%d-%H%M%S}")
                shutil.move(str(dst), str(bk))
                print(f"    an unrelated '{name}' skill existed; moved it to {bk}")
            else:
                shutil.rmtree(dst)
        shutil.copytree(src, dst)
        for md in dst.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            md.write_text(text.replace("{{JHQ}}", cmd).replace("{{APP_DIR}}", ROOT.as_posix()), encoding="utf-8")
        (dst / ".job-hunt-hq").write_text("installed by job-hunt-hq/install.py\n", encoding="utf-8")
        print(f"    {dst}")


def save_config():
    JHQ_HOME.mkdir(parents=True, exist_ok=True)
    cfg_path = JHQ_HOME / "config.json"
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except ValueError:
            cfg = {}
    cfg.update(app_dir=str(ROOT), python=str(venv_python()), command=command())
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"    {cfg_path}")


def remove_skills():
    for name in SKILLS:
        dst = SKILLS_DST / name
        if (dst / ".job-hunt-hq").exists():
            shutil.rmtree(dst)
            print(f"    removed {dst}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args()
    if sys.version_info < (3, 9):
        sys.exit(f"Python 3.9 or newer is needed (this is {sys.version.split()[0]}).")
    if a.check:
        print(f"Would create {VENV}, install requirements, copy {', '.join(SKILLS)} to {SKILLS_DST},\n"
              f"and write {JHQ_HOME / 'config.json'}. Command for Claude: {command()}")
        return
    if a.remove:
        step("Removing the Claude skills (your data folder is not touched)")
        remove_skills()
        return
    step("Python environment")
    make_venv()
    step("Packages")
    install_packages()
    step("Claude skills")
    install_skills()
    step("Config")
    save_config()
    step("Health check")
    subprocess.run([str(venv_python()), "-m", "jhq", "doctor"])
    print("\nDone. Next: in Claude Code, say \"set up Job Hunt HQ\" and answer a few questions.")


if __name__ == "__main__":
    main()
