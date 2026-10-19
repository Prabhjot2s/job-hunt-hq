from jhq import config
from jhq import tracker as trk
from jhq.radar import leads, sync


def test_applied_click_becomes_tracker_row_with_package_estimates(data):
    lead = leads.normalise({"fit": 8, "company": "Acme Analytics", "title": "Data Analyst",
                            "link": "https://example.com/jobs/1", "work_mode": "Hybrid · Chicago",
                            "salary": "$85,000 - $105,000"})
    leads.add_leads([lead], data)
    folder = data.applications / "Acme Analytics - Data Analyst"
    config.write_json(folder / "tracker_meta.json", {
        "company": "Acme Analytics", "title": "Data Analyst", "link": "https://example.com/jobs/1",
        "fields": {"ATS Match When Applied": "80-87%", "ATS Low": 0.8, "ATS High": 0.87, "Emphasis": "SQL; Tableau"}})
    config.write_json(data.lead_status, {lead["id"]: {"status": "Applied", "at": "2026-10-01T10:00"}})

    res = sync.sync(data)
    assert res["added"] == ["APP-001"]
    row = trk.rows(data)[0]
    assert row["Date Applied"] == "2026-10-01" and row["Work Arrangement"] == "Hybrid"
    assert row["ATS Match When Applied"] == "80-87%" and row["Emphasis"] == "SQL; Tableau"
    # running again adds nothing
    assert sync.sync(data).get("added") is None
    assert len(trk.rows(data)) == 1


def test_backfill_only_fills_blank_cells(data):
    trk.add([{"Company": "Globex", "Job Title": "BI Analyst", "Main Gaps": "my own words"}], data)
    folder = data.applications / "Globex - BI Analyst"
    config.write_json(folder / "tracker_meta.json", {
        "company": "Globex", "title": "BI Analyst",
        "fields": {"ATS Match When Applied": "70-78%", "Main Gaps": "overwritten?"}})
    sync.sync(data)
    row = trk.rows(data)[0]
    assert row["ATS Match When Applied"] == "70-78%"
    assert row["Main Gaps"] == "my own words"


def test_demo_builds(tmp_path, monkeypatch):
    from jhq import demo
    monkeypatch.setenv("JHQ_HOME", str(tmp_path / "unused"))
    p = demo.build(tmp_path / "demo")
    assert len(trk.rows(p)) == len(demo.APPS)
    assert len(leads.load(p)) == len(demo.LEADS)
    assert config.read_json(p.skillgap)["jds"] == len(demo.APPS)
