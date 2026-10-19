"""Leads store, shown on the dashboard's Jobs tab.

    jhq leads add reviewed.json     # add judged leads (skips links already stored)
    jhq leads update changes.json   # re-score existing leads by link (old values kept in `history`)
    jhq leads interested            # leads the user starred on the dashboard
    jhq leads links                 # every stored link, for de-duplicating searches
    jhq leads feedback [--days 30]  # skip reasons and likes, to tune scoring
    jhq leads hide <link> [...]     # remove leads that turned out not to fit

reviewed.json: a list of objects with
  fit (1-10), verdict (Strong | Good | Stretch), company, title, location, work_mode, salary,
  currency, years, posted (YYYY-MM-DD), source, link, why, gaps, flags (list), role_family,
  verified (true when the full posting was read and pay, years and work mode are all known)

Files: leads.json is written only here; lead_status.json only by the dashboard (your clicks).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta

from .. import config


def _id(link, company, title):
    return hashlib.sha1((link or f"{company}|{title}").encode("utf-8")).hexdigest()[:12]


def load(paths):
    return config.read_json(paths.leads, []) or []


def save(leads, paths):
    config.write_json(paths.leads, leads)


def _flags(v):
    if isinstance(v, str):
        return [x.strip() for x in v.split(";") if x.strip()]
    return [str(x) for x in (v or []) if str(x).strip()]


def normalise(item, scored_by="claude"):
    now = datetime.now()
    rec = {k: item.get(k) for k in ("fit", "verdict", "company", "title", "tier", "location", "work_mode",
                                    "salary", "currency", "years", "posted", "source", "link", "careers",
                                    "why", "gaps", "role_family")}
    try:
        rec["fit"] = max(1, min(10, int(round(float(item["fit"]))))) if item.get("fit") not in (None, "") else None
    except (TypeError, ValueError):
        rec["fit"] = None
    for k in ("link", "careers"):  # only web links; the dashboard turns these into clickable links
        if rec.get(k) and not str(rec[k]).lower().startswith(("https://", "http://")):
            rec[k] = None
    for k, v in list(rec.items()):
        if v is not None and not isinstance(v, (str, int, float)):
            rec[k] = str(v)
    rec["flags"] = _flags(item.get("flags"))
    if item.get("verified"):
        rec["flags"] = [f for f in rec["flags"] if f != "verified: full posting"] + ["verified: full posting"]
    rec["id"] = _id(rec.get("link"), rec.get("company"), rec.get("title"))
    rec["found"] = config.today().isoformat()
    rec["found_at"] = now.isoformat(timespec="minutes")
    rec["scored_by"] = scored_by
    return {k: v for k, v in rec.items() if v not in (None, "", [])} | {"id": rec["id"]}


def from_candidate(j, fit, why, gaps, scored_by="rules"):
    """A radar candidate -> a lead (used by `radar run --auto-add`)."""
    sal = ", ".join(j.get("salary_hints") or []) or "Not listed"
    return normalise({
        "fit": fit, "verdict": "Strong" if fit >= 8 else "Good" if fit >= 6 else "Stretch",
        "company": j["company"], "title": j["title"], "tier": j.get("tier"),
        "location": j.get("location_label") or j.get("location"), "work_mode": j.get("location_label"),
        "salary": sal, "years": j.get("years_hint"), "posted": (j.get("posted") or "").rstrip("~"),
        "source": f"{j.get('ats', 'company site')} feed", "link": j.get("url"), "careers": j.get("careers"),
        "why": "; ".join(why) or None, "gaps": "; ".join(gaps) or None,
        "flags": (j.get("flags") or []) + ["rules estimate: ask Claude to review"],
    }, scored_by=scored_by)


def add_leads(items, paths):
    leads = load(paths)
    links = {l.get("link") for l in leads if l.get("link")}
    ids = {l["id"] for l in leads}
    added = 0
    for item in items:
        rec = item if "id" in item and "found" in item else normalise(item)
        if (rec.get("link") and rec["link"] in links) or rec["id"] in ids:
            continue
        leads.append(rec)
        links.add(rec.get("link"))
        ids.add(rec["id"])
        added += 1
    save(leads, paths)
    return added


def update_leads(items, paths):
    leads = load(paths)
    by_link = {l.get("link"): l for l in leads}
    changed = 0
    for item in items:
        cur = by_link.get(item.get("link"))
        if not cur:
            continue
        new = normalise(item, scored_by=item.get("scored_by", "claude"))
        old = {k: cur.get(k) for k in ("fit", "verdict", "why", "gaps", "flags", "scored_by")}
        cur.setdefault("history", []).append({"at": datetime.now().isoformat(timespec="minutes"), **old})
        for k, v in new.items():
            if k not in ("id", "found", "found_at"):
                cur[k] = v
        changed += 1
    save(leads, paths)
    return changed


def _row(l):
    """One line per lead: enough for Claude to see patterns (family, mode, pay, years, fit)."""
    return " | ".join(str(x) for x in (
        l.get("company"), l.get("title"), l.get("role_family") or "-", l.get("work_mode") or "-",
        l.get("salary") or "-", f"years {l.get('years', '?')}", f"fit {l.get('fit', '?')}",
        l.get("scored_by", "claude")))


def feedback(paths, days=30):
    """What the user did with the leads: counts, reasons, and every applied / liked / skipped lead."""
    status = config.read_json(paths.lead_status, {}) or {}
    since = (config.today() - timedelta(days=days)).isoformat()
    leads = {l["id"]: l for l in load(paths)}
    skips, likes = Counter(), Counter()
    applied, liked, skipped, interested = [], [], [], []
    for lid, s in status.items():
        l = leads.get(lid)
        if not l or str(s.get("at", ""))[:10] < since:
            continue
        if s.get("status") == "Skipped":
            skips.update(s.get("reasons") or ["no reason"])
            skipped.append(f"{_row(l)} | skipped: {', '.join(s.get('reasons') or []) or 'no reason'}")
        elif s.get("status") == "Applied":
            applied.append(_row(l))
        elif s.get("status") == "Interested":
            interested.append(_row(l))
        if s.get("liked"):
            likes.update(s.get("like_reasons") or ["liked"])
            liked.append(f"{_row(l)} | liked: {', '.join(s.get('like_reasons') or []) or '-'}")
    shown = [l for l in leads.values() if str(l.get("found", "")) >= since]
    untouched = [l for l in shown if l["id"] not in status]
    return {"days": days, "leads_shown": len(shown), "applied": len(applied), "skipped": len(skipped),
            "liked": len(liked), "untouched": len(untouched),
            "skip_reasons": dict(skips.most_common()), "like_reasons": dict(likes.most_common()),
            "applied_leads": applied[-40:], "liked_leads": liked[-40:], "skipped_leads": skipped[-60:],
            "interested_leads": interested[-20:],
            "untouched_high_fit": [_row(l) for l in untouched if (l.get("fit") or 0) >= 8][-20:]}


def main(argv=None):
    config.utf8_console()
    ap = argparse.ArgumentParser(prog="jhq leads")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add"); s.add_argument("json")
    s = sub.add_parser("update"); s.add_argument("json")
    sub.add_parser("interested")
    sub.add_parser("links")
    s = sub.add_parser("feedback"); s.add_argument("--days", type=int, default=30)
    s = sub.add_parser("hide"); s.add_argument("links", nargs="+")
    a = ap.parse_args(argv)
    paths = config.Paths()
    if a.cmd in ("add", "update"):
        with open(a.json, encoding="utf-8") as f:
            items = json.load(f)
        items = items if isinstance(items, list) else [items]
        n = add_leads(items, paths) if a.cmd == "add" else update_leads(items, paths)
        print(f"{a.cmd}: {n} lead(s) -> {paths.leads}")
    elif a.cmd == "interested":
        status = config.read_json(paths.lead_status, {}) or {}
        for l in load(paths):
            if status.get(l["id"], {}).get("status") == "Interested":
                print(f"{l.get('company')} | {l.get('title')} | fit {l.get('fit')} | {l.get('link')}")
    elif a.cmd == "links":
        for l in load(paths):
            if l.get("link"):
                print(l["link"])
    elif a.cmd == "feedback":
        print(json.dumps(feedback(paths, a.days), indent=2, ensure_ascii=False))
    elif a.cmd == "hide":
        leads = load(paths)
        keep = [l for l in leads if l.get("link") not in set(a.links)]
        save(keep, paths)
        print(f"removed {len(leads) - len(keep)} lead(s)")


if __name__ == "__main__":
    main()
