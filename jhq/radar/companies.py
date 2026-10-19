"""Build and keep the radar's company list (radar/companies.csv).

    jhq companies list
    jhq companies find acme.com [globex.com ...]   # find each company's job board from its site
    jhq companies link <job-url> [...]             # which ATS + board a job link belongs to
    jhq companies check <ats> <slug>               # open jobs on a board, and how many match you
    jhq companies add new.json                     # append companies (backup first, no duplicates)
    jhq companies remove "Acme" [...]

new.json: [{"company": "Acme", "ats": "greenhouse", "slug": "acme", "tier": "scaleup", "note": ""}]
tier is free text (e.g. scaleup, enterprise, startup). priority: leave blank, or e.g. "REFERRAL"
to always surface that company's matches (shown as a flag on the lead).
Only boards whose feed works are useful: `find` and `check` confirm that before you add one.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from .. import config
from . import feeds
from .filters import Prefs

FIELDS = ["company", "tier", "ats", "slug", "priority", "note"]
PATTERNS = {
    "workday": r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)",
    "greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)",
    "greenhouse_embed": r"greenhouse\.io/embed/job_board/js\?for=([A-Za-z0-9_-]+)",
    "lever": r"jobs\.lever\.co/([A-Za-z0-9_.-]+)",
    "ashby": r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)",
    "rippling": r"ats\.rippling\.com/([A-Za-z0-9_-]+)",
    "workable": r"apply\.workable\.com/([A-Za-z0-9_-]+)",
    "bamboohr": r"([a-z0-9-]+)\.bamboohr\.com",
    "smartrecruiters": r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)",
    "pinpoint": r"([a-z0-9-]+)\.pinpointhq\.com",
}
UNSUPPORTED = {"icims": r"\.icims\.com", "taleo": r"\.taleo\.net", "successfactors": r"successfactors\.",
               "oracle": r"\.oraclecloud\.com", "jobvite": r"jobvite\.com", "dayforce": r"dayforcehcm\.com"}
BAD = {"www", "api", "boards", "jobs", "app", "careers", "static", "cdn", "embed"}
# Careers pages (not APIs) often serve bots an empty shell, so the page scan looks like a browser.
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def load(paths):
    if not paths.companies.exists():
        return []
    with open(paths.companies, encoding="utf-8", newline="") as f:
        return [{k: (r.get(k) or "").strip() for k in FIELDS} for r in csv.DictReader(f)]


def save(rows, paths):
    paths.companies.parent.mkdir(parents=True, exist_ok=True)
    if paths.companies.exists():
        shutil.copy2(paths.companies, paths.companies.with_name(f"companies.backup-{datetime.now():%Y%m%d-%H%M%S}.csv"))
        old = sorted(paths.companies.parent.glob("companies.backup-*.csv"))
        for f in old[:-10]:
            f.unlink(missing_ok=True)
    tmp = paths.companies.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    tmp.replace(paths.companies)


def parse_link(url):
    """job URL -> (ats, slug, job_id) or None."""
    u = urlparse(url.strip().rstrip(").,"))
    host, parts = (u.hostname or "").lower(), [p for p in u.path.split("/") if p]
    q = parse_qs(u.query)
    if host.endswith("greenhouse.io"):
        if "for" in q:
            return "greenhouse", q["for"][0].lower(), (q.get("token") or [None])[0]
        if len(parts) >= 3 and parts[1] == "jobs" and parts[2].isdigit():
            return "greenhouse", parts[0].lower(), parts[2]
        if parts and parts[0] != "embed":
            return "greenhouse", parts[0].lower(), (q.get("gh_jid") or [None])[0]
    if host in ("jobs.lever.co", "jobs.eu.lever.co") and parts:
        return "lever", parts[0].lower(), parts[1] if len(parts) > 1 else None
    if host == "jobs.ashbyhq.com" and parts:
        return "ashby", parts[0].lower(), parts[1] if len(parts) > 1 else None
    if host == "apply.workable.com" and parts:
        return "workable", parts[0].lower(), parts[2] if len(parts) > 2 and parts[1] == "j" else None
    if host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com") and parts:
        return "smartrecruiters", parts[0], parts[1].split("-")[0] if len(parts) > 1 else None
    if host.endswith(".bamboohr.com"):
        return "bamboohr", host.split(".")[0], parts[1] if len(parts) > 1 else None
    if host.endswith(".pinpointhq.com"):
        return "pinpoint", host.split(".")[0], None
    if host == "ats.rippling.com" and parts:
        return "rippling", parts[0], None
    if host.endswith("myworkdayjobs.com"):
        tenant, wd = host.split(".")[0], host.split(".")[1]
        if parts and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", parts[0]):
            parts = parts[1:]
        if parts:
            path = "/" + "/".join(parts[1:]) if len(parts) > 2 and parts[1] == "job" else None
            return "workday", f"{tenant}|{wd}|{parts[0]}", path
    return None


def board_stats(ats, slug, prefs: Prefs | None = None):
    today = config.today()
    try:
        jobs = list(feeds.FETCHERS[ats](slug, today=today, cutoff=today - timedelta(days=30)))
    except Exception as e:  # noqa: BLE001
        return {"ats": ats, "slug": slug, "ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
    out = {"ats": ats, "slug": slug, "ok": True, "open_jobs": len(jobs)}
    if prefs:
        titles = [j for j in jobs if prefs.title_ok(j["title"])]
        placed = [j for j in titles if prefs.classify(j["location"], j.get("workplace", ""))[0]]
        out.update(title_matches=len(titles), title_and_location_matches=len(placed),
                   examples=[f"{j['title']} ({j['location'][:60]})" for j in placed[:5]])
    return out


GUESS_ATS = ("greenhouse", "lever", "ashby", "workable", "smartrecruiters")


def guess_boards(name):
    """Many careers pages load their jobs with JavaScript, so their HTML has no board link.
    Boards are usually named after the company: try the likely slugs on each public API."""
    base = re.sub(r"^https?://", "", name.strip().lower()).split("/")[0]
    base = re.sub(r"^(www|careers|jobs)\.", "", base).split(".")[0] if "." in base else base
    words = re.findall(r"[a-z0-9]+", base)
    slugs = list(dict.fromkeys(["".join(words), "-".join(words), *(words[:1] if len(words) > 1 else [])]))
    found = {}

    def probe(pair):
        ats, slug = pair
        try:
            jobs = list(feeds.FETCHERS[ats](slug, today=config.today(), cutoff=config.today()))
            return (ats, slug, len(jobs)) if jobs else None
        except Exception:  # noqa: BLE001
            return None

    with ThreadPoolExecutor(8) as ex:
        for hit in ex.map(probe, [(a, s) for a in GUESS_ATS for s in slugs if s]):
            if hit and hit[0] not in found:
                found[hit[0]] = hit[1]
    return found


def find(domain):
    dom = re.sub(r"^https?://", "", domain.strip()).strip("/")
    base = dom.split("/")[0]
    if "." not in base:  # a company name, not a website
        found = guess_boards(domain)
        return {"domain": domain, "found": found, "method": "slug guess"} if found else \
            {"domain": domain, "found": {}, "hint": "No board found by name. Give the company's website instead."}
    tries = ([f"https://{dom}"] if "/" in dom else []) + [
        f"https://{base}/careers", f"https://www.{base}/careers", f"https://{base}/jobs",
        f"https://careers.{base}", f"https://jobs.{base}", f"https://www.{base}/company/careers",
        f"https://{base}"]
    found, unsupported = {}, []
    for u in tries:
        try:
            r = feeds.S.get(u, timeout=12, headers={"Accept": "text/html", "User-Agent": BROWSER_UA})
        except Exception:  # noqa: BLE001
            continue
        text = r.url + " " + r.text[:800000]
        for ats, pat in PATTERNS.items():
            for m in re.finditer(pat, text):
                g = m.groups()
                if ats != "workday" and g[0].lower() in BAD:
                    continue
                found.setdefault(ats.replace("_embed", ""), "|".join(g))
        unsupported += [n for n, pat in UNSUPPORTED.items() if re.search(pat, text) and n not in unsupported]
        if found:
            return {"domain": domain, "page": u, "found": found}
    guessed = guess_boards(base)
    if guessed:
        return {"domain": domain, "found": guessed, "method": "slug guess (careers page loads jobs with JavaScript)"}
    return {"domain": domain, "found": {}, "unsupported_ats": unsupported,
            "hint": "No supported job board found. Try the careers page URL directly, or a job link "
                    "from a web search with `jhq companies link`."}


def main(argv=None):
    config.utf8_console()
    ap = argparse.ArgumentParser(prog="jhq companies")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("find"); s.add_argument("domains", nargs="+")
    s = sub.add_parser("link"); s.add_argument("urls", nargs="+")
    s = sub.add_parser("check"); s.add_argument("ats", choices=list(feeds.FETCHERS)); s.add_argument("slug")
    s = sub.add_parser("add"); s.add_argument("json")
    s = sub.add_parser("remove"); s.add_argument("names", nargs="+")
    a = ap.parse_args(argv)
    paths = config.Paths()
    prefs = Prefs(config.prefs(paths)) if paths.prefs.exists() else None

    if a.cmd == "list":
        rows = load(paths)
        for r in rows:
            print(f"{r['company']} | {r['ats']} | {r['slug']} | {r['tier']} {('| ' + r['priority']) if r['priority'] else ''}")
        print(f"# {len(rows)} companies")
    elif a.cmd == "find":
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(find, a.domains))
        for r in res:
            for ats, slug in r.get("found", {}).items():
                if feeds.valid_slug(ats, slug):
                    r.setdefault("boards", []).append(board_stats(ats, slug, prefs))
        print(json.dumps(res, indent=1, ensure_ascii=False))
    elif a.cmd == "link":
        known = {(r["ats"], r["slug"].lower()) for r in load(paths)}
        for u in a.urls:
            p = parse_link(u)
            if not p:
                print(json.dumps({"url": u, "ats": None, "note": "not a supported ATS link"}))
                continue
            ats, slug, jid = p
            print(json.dumps({"url": u, "ats": ats, "slug": slug, "job": jid,
                              "already_tracked": (ats, slug.lower()) in known,
                              **({} if (ats, slug.lower()) in known else {"board": board_stats(ats, slug, prefs)})},
                             ensure_ascii=False))
    elif a.cmd == "check":
        print(json.dumps(board_stats(a.ats, a.slug, prefs), indent=1, ensure_ascii=False))
    elif a.cmd == "add":
        with open(a.json, encoding="utf-8") as f:
            new = json.load(f)
        rows = load(paths)
        have = {(r["ats"], r["slug"].lower()) for r in rows} | {("name", r["company"].lower()) for r in rows}
        added, skipped = [], []
        for n in new if isinstance(new, list) else [new]:
            n = {k: str(n.get(k) or "").strip() for k in FIELDS}
            if n["ats"] not in feeds.FETCHERS or not feeds.valid_slug(n["ats"], n["slug"]) or not n["company"]:
                skipped.append(f"{n['company'] or '?'}: bad ats/slug")
                continue
            if (n["ats"], n["slug"].lower()) in have or ("name", n["company"].lower()) in have:
                skipped.append(f"{n['company']}: already listed")
                continue
            rows.append(n)
            have |= {(n["ats"], n["slug"].lower()), ("name", n["company"].lower())}
            added.append(n["company"])
        save(rows, paths)
        print(json.dumps({"added": added, "skipped": skipped, "total": len(rows)}, indent=1))
    elif a.cmd == "remove":
        rows = load(paths)
        drop = {n.lower() for n in a.names}
        keep = [r for r in rows if r["company"].lower() not in drop]
        save(keep, paths)
        print(f"removed {len(rows) - len(keep)}; {len(keep)} left")


if __name__ == "__main__":
    main()
