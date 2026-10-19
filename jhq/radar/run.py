"""Daily radar run: fetch every tracked company's job feed, keep fresh postings that match.

    jhq radar run                 # window from preferences (default: today + yesterday)
    jhq radar run --only "Acme"   # one or more companies (comma list)
    jhq radar run --days 3 --dry-run
    jhq radar run --auto-add      # also save matches as leads with a rules-based fit score
                                  # (for scheduled runs without Claude; Claude can rescore later)

Writes radar/runs/candidates_<stamp>.json (path printed last). Each job carries years_hint,
years_lines (the actual requirement sentences) and salary_hints, read from the full posting;
`desc` is an excerpt (opening + every years/pay/work-mode/requirements line).
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from .. import config
from .. import tracker as trk
from . import feeds
from .filters import Prefs, rules_fit


def load_companies(paths):
    if not paths.companies.exists():
        return []
    with open(paths.companies, encoding="utf-8", newline="") as f:
        out = []
        for c in csv.DictReader(f):
            c = {k: (v or "").strip() for k, v in c.items() if k}
            if c.get("ats") in feeds.FETCHERS and c.get("slug") and feeds.valid_slug(c["ats"], c["slug"]):
                out.append(c)
        return out


_FILLER = {"inc", "ltd", "llc", "corp", "corporation", "co", "company", "the", "group", "limited", "&", "and"}


def _co_tokens(name):
    words = re.findall(r"[a-z0-9&]+", name.lower().split(" (")[0])
    return {w for w in words if w not in _FILLER} or set(words)


def tracked_pairs(paths):
    try:
        return [(str(r.get("Company", "")).lower(), str(r.get("Job Title", "")).lower())
                for r in trk.rows(paths) if r.get("Company") and r.get("Job Title")]
    except SystemExit:
        return []


def in_tracker(company, title, pairs):
    c, ct = company.lower().split(" (")[0], _co_tokens(company)
    for tc, tt in pairs:
        tt_tokens = _co_tokens(tc)
        same = c in tc or tc in c or ct <= tt_tokens or tt_tokens <= ct
        if same and difflib.SequenceMatcher(None, title.lower(), tt).ratio() > 0.8:
            return True
    return False


def skill_patterns(paths):
    """The user's strong/working skills from the taxonomy, for the rules score."""
    tax = config.read_json(paths.taxonomy) or {}
    out = []
    for s in tax.get("skills", []):
        if s.get("level") in ("strong", "working") and s.get("re"):
            out.append((s["skill"], re.compile(r"(?<![a-z0-9])(?:" + "|".join(s["re"]) + r")(?![a-z0-9])", re.I)))
    return out


def main(argv=None):
    config.utf8_console()
    ap = argparse.ArgumentParser(prog="jhq radar run")
    ap.add_argument("--days", type=int, help="window incl. today (2 = today + yesterday)")
    ap.add_argument("--only", help="comma list of company names")
    ap.add_argument("--dry-run", action="store_true", help="don't update radar state")
    ap.add_argument("--auto-add", action="store_true", help="save matches as rules-scored leads")
    a = ap.parse_args(argv)

    paths = config.Paths()
    prefs = Prefs(config.prefs(paths))
    today = config.today()
    days = a.days or prefs.window_days
    cutoff = today - timedelta(days=days - 1)
    companies = load_companies(paths)
    if a.only:
        want = {x.strip().lower() for x in a.only.split(",")}
        companies = [c for c in companies if c["company"].lower() in want]
    if not companies:
        raise SystemExit(f"No companies to check. Add some to {paths.companies} "
                         "(ask Claude: 'find companies for my radar').")

    state = config.read_json(paths.seen, None) or {"seen": {}, "baselined": [], "reported": {}, "last_run": {}}
    seen, baselined = state["seen"], set(state["baselined"])
    reported = state.setdefault("reported", {})
    scope = a.only.lower() if a.only else "all"
    last = state.setdefault("last_run", {}).get(scope)
    if last and not a.dry_run:  # catch up after missed days (PC off), at most a week
        cutoff = max(min(cutoff, date.fromisoformat(last)), today - timedelta(days=6))
    pairs = tracked_pairs(paths)

    def fetch(c):
        try:
            jobs = list(feeds.FETCHERS[c["ats"]](c["slug"], today=today, cutoff=cutoff))
            return c, jobs, None
        except Exception as e:  # noqa: BLE001
            return c, [], f"{type(e).__name__}: {str(e)[:150]}"

    with ThreadPoolExecutor(12) as ex:
        results = list(ex.map(fetch, companies))

    cands, errors, needs_detail = [], [], []
    stats = dict(companies=len(companies), jobs_scanned=0, title_match=0)
    for c, jobs, err in results:
        if err:
            errors.append({"company": c["company"], "error": err})
            continue
        stats["jobs_scanned"] += len(jobs)
        first_time = c["company"] not in baselined
        for j in jobs:
            key = f"{c['company']}::{j['id']}"
            is_new = key not in seen
            if is_new:
                seen[key] = today.isoformat()
            if not prefs.title_ok(j["title"]):
                continue
            stats["title_match"] += 1
            posted = (j.get("posted") or "").rstrip("~")
            fresh = posted >= cutoff.isoformat() if posted else (is_new and not first_time)
            if not fresh or key in reported:
                continue
            j["_key"] = key
            j.update(company=c["company"], tier=c.get("tier", ""), ats=c["ats"], priority=c.get("priority", ""),
                     company_note=c.get("note", ""), first_seen=seen[key],
                     careers=feeds.careers_url(c["ats"], c["slug"]),
                     date_basis="posted" if posted else "first seen by radar")
            if j.get("_detail"):
                needs_detail.append(j)
            cands.append(j)
        baselined.add(c["company"])

    with ThreadPoolExecutor(12) as ex:
        list(ex.map(feeds.detail, needs_detail))

    keep, dropped = [], {}
    for j in cands:
        ok, label, flags = prefs.classify(j["location"], j.get("workplace", ""))
        if not ok and not j["priority"]:
            dropped[label] = dropped.get(label, 0) + 1
            continue
        if in_tracker(j["company"], j["title"], pairs):
            dropped["already in tracker"] = dropped.get("already in tracker", 0) + 1
            continue
        j.pop("_detail", None)
        reported[j.pop("_key")] = today.isoformat()
        if j["priority"]:  # "★" marks a priority company on the dashboard
            flags.insert(0, f"★ {j['priority']}: {j['company_note']}".rstrip(": "))
        j["location_label"], j["flags"] = label, flags
        j["salary_hints"] = ([j["salary"]] if j.get("salary") else []) + feeds.salary_hints(j["desc"])
        j["years_hint"] = feeds.years_hint(j["desc"])
        j["years_lines"] = feeds.years_lines(j["desc"])
        j["desc_chars"] = len(j["desc"])
        j["desc"] = feeds.excerpt(j["desc"])
        keep.append(j)

    keep.sort(key=lambda j: (not j["priority"], j["company"]))
    paths.runs.mkdir(parents=True, exist_ok=True)
    out = paths.runs / f"candidates_{datetime.now():%Y-%m-%d_%H%M%S}.json"
    stats.update(window=f"{cutoff} to {today}", candidates=len(keep), dropped=dropped, feed_errors=len(errors))
    config.write_json(out, {"stats": stats, "errors": errors, "jobs": keep})
    if not a.dry_run:
        state["last_run"][scope] = today.isoformat()
        config.write_json(paths.seen, {"seen": seen, "baselined": sorted(baselined), "reported": reported,
                                       "last_run": state["last_run"]}, indent=None)
    if a.auto_add and keep:
        from . import leads as leads_mod
        skill_rx = skill_patterns(paths)
        targets = (config.read_json(paths.profile, {}) or {}).get("target_titles") or []
        scored = []
        for j in keep:
            j["_pay"] = feeds.salary_range(j["salary_hints"])
            fit, why, gaps = rules_fit(j, prefs, skill_rx, targets)
            scored.append(leads_mod.from_candidate(j, fit, why, gaps, scored_by="rules"))
        added = leads_mod.add_leads(scored, paths)
        stats["auto_added"] = added
    print(json.dumps(stats, ensure_ascii=False))
    for j in keep:
        print(f"- [{j['priority'] or j['tier'] or '-'}] {j['company']} | {j['title']} | {j['location_label']} | "
              f"posted {j.get('posted') or '?'} | yrs {j['years_hint']} | {', '.join(j['salary_hints'][:2])}")
    print(out)


if __name__ == "__main__":
    main()
