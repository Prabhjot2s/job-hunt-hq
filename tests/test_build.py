import json
import shutil

import pytest

from jhq import build_package, config, pdf_export
from conftest import ALEX

needs_pdf = pytest.mark.skipif(not pdf_export.available(), reason="needs Microsoft Word or LibreOffice")


def _spec(tmp_path):
    shutil.copy(ALEX / "jd_acme.txt", tmp_path / "jd_acme.txt")
    spec = json.loads((ALEX / "spec_acme.json").read_text(encoding="utf-8"))
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    return p, spec


@needs_pdf
def test_full_package(data, tmp_path):
    spec_path, _ = _spec(tmp_path)
    rep = build_package.run(spec_path, qa_dir=tmp_path / "qa", paths=data)
    names = set(rep["files"])
    assert {"Alex_Sample_Resume.pdf", "Alex_Sample_Resume.docx", "Alex_Sample_Cover_Letter.pdf",
            "Job Description.docx"} <= names
    assert rep["pages"] == 1
    assert rep["ats"]["keyword_coverage_pct"] >= 80
    assert not rep["ats"]["missing_required"]
    assert not any("missing" in w and "link" in w for w in rep["warnings"])
    meta = config.read_json(rep["tracker_meta"])
    assert meta["company"] == "Acme Analytics" and meta["fields"]["Cover Letter"] == "Yes"
    assert 0.8 <= meta["fields"]["Keyword Coverage"] <= 1
    assert rep["cover_letter"]["pages"] == 1 and not rep["cover_letter"]["warnings"]
    # refuses to overwrite without --overwrite
    with pytest.raises(SystemExit):
        build_package.run(spec_path, qa_dir=tmp_path / "qa", paths=data)


@needs_pdf
def test_forbidden_phrase_is_caught(data, tmp_path):
    spec_path, spec = _spec(tmp_path)
    spec["resume"]["certifications"] = ["Expired Example Certification"]
    spec.pop("cover_letter")
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    rep = build_package.run(spec_path, qa_dir=tmp_path / "qa", paths=data)
    assert any("forbidden" in w for w in rep["warnings"])


def test_never_writes_outside_applications(data, tmp_path):
    spec = {"folder": str(tmp_path / "elsewhere"), "cover_letter": {"paragraphs": ["x"]}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(SystemExit):
        build_package.run(p, paths=data)
    spec["folder"] = "../../escape"
    p.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(SystemExit):
        build_package.run(p, paths=data)


def test_safe_folder_names():
    assert config.safe_name('Acme: "Data/BI" Analyst?') == "Acme- -Data-BI- Analyst"
    assert config.safe_name("...") == "untitled"


def test_init_refuses_data_inside_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("JHQ_HOME", str(tmp_path / "home"))
    from jhq import cli
    with pytest.raises(SystemExit):
        cli.cmd_init(["--data-dir", str(config.APP_DIR / "my-data")])
