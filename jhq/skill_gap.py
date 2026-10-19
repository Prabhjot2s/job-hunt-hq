"""Skill-gap heatmap: what your saved job descriptions ask for vs. what you can truthfully claim.

    jhq skillgap [--print]

Reads every applications/<Company> - <Job Title>/Job Description.docx, matches it to its tracker
row (tracker_meta.json first, then the folder name), finds skills with profile/skill_taxonomy.json
and writes skill-gap/skill_gap.json for the dashboard's Skills tab.

Gap score = share of job descriptions asking for the skill x (1 - your level).
Idea and weighting adapted from MadsLorentzen/ai-job-search (MIT), /upskill.
Callback columns are directional only: there are rarely enough outcomes to call them causes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import re
import sys
from collections import Counter, defaultdict

from docx import Document

from . import config
from . import tracker as trk

POSITIVE = {"Callback", "Interview", "Offer"}


def jd_text(path):
    paras = [p.text for p in Document(path).paragraphs]
    for i, t in enumerate(paras):
        if t.strip().upper() == "ORIGINAL JOB DESCRIPTION":
            return "\n".join(paras[i + 1:])
    return "\n".join(paras)


def compile_taxonomy(paths):
    tax = config.read_json(paths.taxonomy) or config.read_json(config.TEMPLATES / "profile" / "skill_taxonomy.json")
    for s in tax["skills"]:
        s["rx"] = re.compile(r"(?<![a-z0-9])(?:" + "|".join(s["re"]) + r")(?![a-z0-9])", re.I)
    return tax


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def match_row(folder, rows):
    meta = config.read_json(folder / "tracker_meta.json", {}) or {}
    company, title = meta.get("company"), meta.get("title")
    if not company and " - " in folder.name:
        company, title = folder.name.split(" - ", 1)
    key = norm(f"{company} {title}")
    best, score = None, 0.0
    for r in rows:
        rc = norm(r.get("Company"))
        if rc and rc.split()[0] not in key and norm(company) not in rc:
            continue
        s = difflib.SequenceMatcher(None, key, norm(f"{r.get('Company')} {r.get('Job Title')}")).ratio()
        if s > score:
            best, score = r, s
    return (best, company, title) if score >= 0.6 else (None, company, title)


def positive(row):
    return bool(row) and (row.get("Final Outcome") in POSITIVE or bool(row.get("Callback Date")))


def analyse(paths):
    tax = compile_taxonomy(paths)
    levels = tax["levels"]
    try:
        rows = trk.rows(paths)
    except SystemExit:
        rows = []
    jobs = []
    for jd in sorted(paths.applications.glob("*/Job Description.docx")):
        folder = jd.parent
        try:
            text = jd_text(jd)
        except Exception as e:  # noqa: BLE001
            print(f"skip {folder.name}: {e}", file=sys.stderr)
            continue
        row, company, title = match_row(folder, rows)
        jobs.append({
            "folder": folder.name, "company": company, "title": title,
            "app_id": row.get("Application ID") if row else None, "applied": bool(row),
            "family": (row.get("Job Family") if row else None) or ("Other" if row else "Not applied"),
            "status": row.get("Status") if row else None, "positive": positive(row),
            "skills": [s["skill"] for s in tax["skills"] if s["rx"].search(text)],
        })

    n = len(jobs)
    fam_count = Counter(j["family"] for j in jobs)
    families = [f for f, c in fam_count.most_common() if c >= 3 and f != "Not applied"][:7]
    by_skill = defaultdict(list)
    for j in jobs:
        for s in j["skills"]:
            by_skill[s].append(j)
    out = []
    for s in tax["skills"]:
        hits = by_skill.get(s["skill"], [])
        demand = len(hits) / n if n else 0
        applied = [j for j in hits if j["applied"]]
        out.append({
            "skill": s["skill"], "category": s["cat"], "level": s["level"], "jds": len(hits),
            "demand_pct": round(100 * demand, 1),
            "gap_score": round(100 * demand * (1 - levels[s["level"]]), 1),
            "by_family": {f: round(100 * sum(1 for j in hits if j["family"] == f) / fam_count[f], 1)
                          for f in families},
            "applied_with_skill": len(applied),
            "positive_with_skill": sum(1 for j in applied if j["positive"]),
            "examples": [f"{j['company']} - {j['title']}" for j in hits[:4]],
        })
    out.sort(key=lambda x: (-x["gap_score"], -x["demand_pct"]))
    return {
        "generated": dt.datetime.now().isoformat(timespec="minutes"),
        "jds": n, "applied": sum(1 for j in jobs if j["applied"]),
        "positive_outcomes": sum(1 for j in jobs if j["positive"]),
        "tracker_callbacks": sum(1 for r in rows if positive(r)),
        "families": [{"family": f, "jds": fam_count[f]} for f in families],
        "levels": levels, "skills": out,
        "jobs": [{k: j[k] for k in ("folder", "app_id", "family", "status", "positive", "skills")} for j in jobs],
        "note": "Demand = share of saved job descriptions that mention the skill. Gap = demand x "
                "(1 - your level). Callback columns are directional only (few outcomes).",
    }


def main(argv=None):
    config.utf8_console()
    ap = argparse.ArgumentParser(prog="jhq skillgap")
    ap.add_argument("--print", action="store_true", help="print the top gaps as a table")
    a = ap.parse_args(argv)
    paths = config.Paths()
    data = analyse(paths)
    config.write_json(paths.skillgap, data)
    print(f"{data['jds']} job descriptions ({data['applied']} matched to tracker rows) -> {paths.skillgap}")
    if a.print:
        print("\n| Skill | Your level | JDs asking | Demand | Gap score | Callbacks when asked |")
        print("|---|---|---:|---:|---:|---|")
        for s in data["skills"][:25]:
            if s["jds"]:
                print(f"| {s['skill']} | {s['level']} | {s['jds']} | {s['demand_pct']}% | {s['gap_score']} "
                      f"| {s['positive_with_skill']}/{s['applied_with_skill']} |")


if __name__ == "__main__":
    main()
