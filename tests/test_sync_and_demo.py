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


def test_feedback_lists_each_lead_with_reasons(data):
    a = leads.normalise({"fit": 9, "company": "Acme", "title": "Senior Analyst", "link": "https://example.com/a"})
    b = leads.normalise({"fit": 8, "company": "Globex", "title": "Analyst", "link": "https://example.com/b"})
    c = leads.normalise({"fit": 9, "company": "Initech", "title": "BI Analyst", "link": "https://example.com/c"})
    leads.add_leads([a, b, c], data)
    today = config.today().isoformat()
    config.write_json(data.lead_status, {
        a["id"]: {"status": "Skipped", "reasons": ["Too senior"], "at": today},
        b["id"]: {"status": "Applied", "at": today, "liked": True, "like_reasons": ["Remote"]}})
    fb = leads.feedback(data, days=7)
    assert fb["skip_reasons"] == {"Too senior": 1}
    assert "Too senior" in fb["skipped_leads"][0] and "Acme" in fb["skipped_leads"][0]
    assert "Globex" in fb["applied_leads"][0] and "Remote" in fb["liked_leads"][0]
    assert any("Initech" in r for r in fb["untouched_high_fit"])


def test_learned_rules_are_dated_and_capped(data):
    from jhq.radar import learn
    learn.main(["add", "6 of 9 skips were Too senior: cap 4+ yr roles at fit 6"])
    rules = learn.load(data)
    assert rules[0].startswith(config.today().isoformat()) and "cap 4+" in rules[0]
    for i in range(25):
        learn.main(["add", f"rule {i}"])
    assert len(learn.load(data)) == learn.MAX_RULES
    learn.main(["remove", "1"])
    assert len(learn.load(data)) == learn.MAX_RULES - 1


def test_radar_stats_flags_feeds_failing_three_times(data):
    from jhq.radar import stats
    for i in range(4):
        config.write_json(data.runs / f"candidates_2026-10-1{i}_170000.json", {
            "stats": {"companies": 2, "jobs_scanned": 100, "title_match": 5, "candidates": 2, "feed_errors": 1},
            "errors": [{"company": "Gone Co", "error": "HTTPError: 404"}] if i else [], "jobs": []})
    s = stats.stats(data, last=7)
    assert s["runs_read"] == 4 and s["candidates_total"] == 8
    assert s["broken_feeds"] == [{"company": "Gone Co", "failed_runs": 3, "last_error": "HTTPError: 404"}]
