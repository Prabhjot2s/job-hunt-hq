import datetime as dt

import pytest

from jhq import config
from jhq import tracker as trk


def test_add_assigns_ids_and_defaults(data):
    res = trk.add([{"Company": "Acme", "Job Title": "Data Analyst", "Date Applied": "today",
                    "ATS Low": "80%", "ATS High": 0.87, "Salary Min": "85,000"},
                   {"Company": "Globex", "Job Title": "BI Analyst", "Date Applied": "2026-01-02"}], data)
    ids = [r["Application ID"] for r in res["added"]]
    assert ids == ["APP-001", "APP-002"]
    rows = trk.rows(data)
    assert rows[0]["Status"] == "Applied" and rows[0]["Final Outcome"] == "Pending"
    assert rows[0]["ATS Low"] == 0.8 and rows[0]["Salary Min"] == 85000
    assert rows[0]["Status Updated"] == config.today().isoformat()
    assert res["backup"] is not None


def test_ids_continue_after_existing_rows(data):
    trk.add([{"Company": "A", "Job Title": "X"}], data)
    trk.add([{"Company": "B", "Job Title": "Y"}], data)
    assert [r["Application ID"] for r in trk.rows(data)] == ["APP-001", "APP-002"]


def test_rejects_unknown_column_and_bad_values(data):
    with pytest.raises(SystemExit):
        trk.add([{"Company": "A", "Job Title": "X", "Favourite Colour": "blue"}], data)
    with pytest.raises(SystemExit):
        trk.add([{"Company": "A", "Job Title": "X", "Status": "Maybe"}], data)
    with pytest.raises(SystemExit):
        trk.add([{"Company": "A", "Job Title": "X", "Date Applied": "last tuesday"}], data)
    with pytest.raises(SystemExit):
        trk.add([{"Company": "A"}], data)  # no title
    assert trk.rows(data) == []  # nothing half-written


def test_protected_fields_need_explicit_permission(data):
    trk.add([{"Company": "A", "Job Title": "X", "ATS Low": 0.8}], data)
    with pytest.raises(SystemExit):
        trk.update([{"id": "APP-001", "fields": {"ATS Low": 0.5}}], data)
    trk.update([{"id": "APP-001", "fields": {"ATS Low": 0.5}}], data, allow_protected=True)
    assert trk.rows(data)[0]["ATS Low"] == 0.5


def test_notes_append(data):
    trk.add([{"Company": "A", "Job Title": "X", "Notes": "first"}], data)
    trk.update([{"id": "APP-001", "fields": {"Notes+": "second"}}], data)
    assert trk.rows(data)[0]["Notes"] == "first; second"


def test_events_set_fields_and_keep_dates(data):
    trk.add([{"Company": "A", "Job Title": "X", "Date Applied": "2026-01-02"}], data)
    trk.event("APP-001", "screen", date="2026-01-10", paths=data)
    trk.event("APP-001", "rejected", date="2026-01-20", note="after screen", paths=data)
    r = trk.rows(data)[0]
    assert r["Status"] == "Rejected" and r["Outcome Stage"] == "Closed"
    assert r["Callback Date"] == "2026-01-10"  # never cleared by a later rejection
    assert r["Rejection Date"] == "2026-01-20" and "after screen" in r["Notes"]


def test_aging_lists_only_quiet_pending_rows(data):
    old = (config.today() - dt.timedelta(days=45)).isoformat()
    trk.add([{"Company": "Quiet", "Job Title": "X", "Date Applied": old},
             {"Company": "Called", "Job Title": "Y", "Date Applied": old, "Callback Date": old},
             {"Company": "Fresh", "Job Title": "Z", "Date Applied": "today"},
             {"Company": "NoDate", "Job Title": "W"}], data)
    eligible, skipped = trk.aging(30, data)
    assert [r["Company"] for r in eligible] == ["Quiet"]
    assert [r["Company"] for r in skipped] == ["NoDate"]


def test_refuses_when_excel_lock_file_exists(data):
    trk.init(data)
    lock = data.tracker.parent / f"~${data.tracker.name}"
    lock.write_text("x")
    with pytest.raises(SystemExit):
        trk.add([{"Company": "A", "Job Title": "X"}], data)
