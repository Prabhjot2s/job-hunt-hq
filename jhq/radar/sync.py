"""Copy leads you marked "Applied" on the dashboard into the tracker.

    jhq radar sync [--dry-run]

Runs by itself about a minute after an "Applied" click (the dashboard starts it) and on every
radar run, so a failed attempt (tracker open in Excel) simply retries later.

When a tailored package was built for the job, its folder holds tracker_meta.json (estimates,
strategy, strengths, gaps). New rows are filled from it, and rows whose estimate cells are still
blank are backfilled once a matching tracker_meta.json exists. Only blank cells are filled.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re

from .. import config
from .. import tracker as trk
from .leads import load as load_leads
from .run import in_tracker

MODES = {"remote": "Remote", "hybrid": "Hybrid", "on-site": "On-site", "onsite": "On-site"}


def _norm(x):
    return re.sub(r"[^a-z0-9]+", " ", str(x or "").lower()).strip()


def metas(paths):
    out = []
    for p in paths.applications.glob("*/tracker_meta.json"):
        m = config.read_json(p, None)
        if isinstance(m, dict) and m.get("company"):
            out.append(m)
    return out


def find_meta(company, title, link, all_metas):
    if link:
        for m in all_metas:
            if m.get("link") and m["link"].rstrip("/") == link.rstrip("/"):
                return m
    best, score = None, 0.0
    for m in all_metas:
        if _norm(m.get("company")) != _norm(company) and _norm(company) not in _norm(m.get("company")):
            continue
        s = difflib.SequenceMatcher(None, _norm(title), _norm(m.get("title"))).ratio()
        if s > score:
            best, score = m, s
    return best if score >= 0.75 else None


def row_for(lead, status, meta):
    mode = next((v for k, v in MODES.items() if k in str(lead.get("work_mode", "")).lower()), None)
    row = {"Company": lead.get("company"), "Job Title": lead.get("title"),
           "Date Applied": str(status.get("at", ""))[:10] or "today",
           "Location": lead.get("location"), "Work Arrangement": mode,
           "Salary Range": lead.get("salary") if lead.get("salary") not in (None, "Not listed") else None,
           "Currency": lead.get("currency"), "Job Source / URL": lead.get("link"),
           "Job Family": lead.get("role_family"),
           "Notes": "Added from the Jobs tab (Applied click)."}
    if meta:
        row.update({k: v for k, v in (meta.get("fields") or {}).items() if k in trk.HEADERS})
    return {k: v for k, v in row.items() if v not in (None, "")}


def backfill(paths, dry):
    all_metas = metas(paths)
    ups = []
    for r in trk.rows(paths):
        if r.get("ATS Match When Applied") or r.get("Keyword Coverage"):
            continue
        m = find_meta(r.get("Company"), r.get("Job Title"), r.get("Job Source / URL"), all_metas)
        if not m:
            continue
        fields = {k: v for k, v in (m.get("fields") or {}).items()
                  if k in trk.HEADERS and k != "Application ID" and r.get(k) in (None, "")}
        if fields:
            ups.append({"id": r["Application ID"], "fields": fields})
    if ups and not dry:
        trk.update(ups, paths, allow_protected=True)  # fills blanks only (checked above)
    return [u["id"] for u in ups]


def sync(paths=None, dry=False):
    paths = paths or config.Paths()
    status = config.read_json(paths.lead_status, {}) or {}
    synced = config.read_json(paths.synced, {}) or {}
    leads = {l["id"]: l for l in load_leads(paths)}
    all_metas = metas(paths)
    trk.init(paths)
    pairs = [(str(r.get("Company", "")).lower(), str(r.get("Job Title", "")).lower(), r["Application ID"])
             for r in trk.rows(paths)]
    todo, already = [], []
    for lid, s in status.items():
        if s.get("status") != "Applied" or lid in synced or lid not in leads:
            continue
        l = leads[lid]
        match = next((i for c, t, i in pairs if in_tracker(l.get("company", ""), l.get("title", ""), [(c, t)])), None)
        if match:
            already.append((lid, match))
            continue
        todo.append((lid, row_for(l, s, find_meta(l.get("company"), l.get("title"), l.get("link"), all_metas))))
    result = {"to_add": len(todo), "already_tracked": len(already)}
    if dry:
        result["rows"] = [r for _, r in todo]
        return result
    if todo:
        res = trk.add([r for _, r in todo], paths)
        for (lid, _), w in zip(todo, res["added"]):
            synced[lid] = w["Application ID"]
        result["added"] = [w["Application ID"] for w in res["added"]]
        result["backup"] = res["backup"]
    for lid, app_id in already:
        synced[lid] = app_id
    if todo or already:
        config.write_json(paths.synced, synced)
    result["backfilled"] = backfill(paths, dry)
    return result


def main(argv=None):
    config.utf8_console()
    ap = argparse.ArgumentParser(prog="jhq radar sync")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    print(json.dumps(sync(dry=a.dry_run), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
