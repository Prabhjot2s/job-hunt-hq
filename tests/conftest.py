import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ALEX = ROOT / "examples" / "alex-sample"


@pytest.fixture()
def data(tmp_path, monkeypatch):
    """A fresh JHQ_HOME + data folder set up for the fictional Alex Sample."""
    monkeypatch.setenv("JHQ_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("JHQ_NO_SYNC", "1")
    from jhq import cli, config
    cli.cmd_init(["--data-dir", str(tmp_path / "data"), "--timezone", "America/Chicago"])
    p = config.Paths()
    shutil.copy(ALEX / "profile.json", p.profile)
    shutil.copy(ALEX / "facts.md", p.facts)
    return p
