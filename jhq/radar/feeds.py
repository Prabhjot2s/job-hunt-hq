"""Public job-board feeds that companies publish through their applicant tracking system (ATS).

These are the same JSON endpoints the companies' own careers pages load. No login, no scraping
of job sites: one request per company board. Supported: Greenhouse, Lever, Ashby, Workable,
SmartRecruiters, Rippling, Pinpoint, BambooHR and Workday.

companies.csv columns: company, tier, ats, slug, priority, note
  slug examples: greenhouse "stripe", lever "plaid", ashby "notion",
                 workday "tenant|wd5|site" (from https://tenant.wd5.myworkdayjobs.com/site)
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone

import requests

UA = "job-hunt-hq (personal job search; github.com/Prabhjot2s/job-hunt-hq)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "application/json"})
T = 20

CAREERS = {
    "greenhouse": "https://job-boards.greenhouse.io/{s}",
    "lever": "https://jobs.lever.co/{s}",
    "ashby": "https://jobs.ashbyhq.com/{s}",
    "workable": "https://apply.workable.com/{s}/",
    "smartrecruiters": "https://careers.smartrecruiters.com/{s}",
    "rippling": "https://ats.rippling.com/{s}/jobs",
    "pinpoint": "https://{s}.pinpointhq.com/",
    "bamboohr": "https://{s}.bamboohr.com/careers",
}


def careers_url(ats, slug):
    if ats == "workday" and slug.count("|") == 2:
        tenant, wd, site = slug.split("|")
        return f"https://{tenant}.{wd}.myworkdayjobs.com/{site}"
    tpl = CAREERS.get(ats)
    return tpl.format(s=slug) if tpl else ""


SLUG_OK = re.compile(r"^[A-Za-z0-9_.%-]+$")


def valid_slug(ats, slug):
    """Slugs end up in URLs: allow only plain board names (Workday: three plain parts)."""
    if ats == "workday":
        parts = slug.split("|")
        return len(parts) == 3 and all(SLUG_OK.match(p) for p in parts) and re.fullmatch(r"wd\d+", parts[1])
    return bool(SLUG_OK.match(slug or ""))


# ---------------------------------------------------------------- text helpers
def clean(text, limit=None):
    t = html.unescape(text or "")
    t = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<li[^>]*>", "- ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    return t[:limit] if limit else t


SAL = re.compile(r"(?:(?:CA|US|C|CAD|USD|GBP|EUR|AUD)?\s?[$£€]\s?\d[\d,]*(?:\.\d+)?\s?[kK]?"
                 r"(?:\s?(?:-|–|—|to)\s?(?:CA|US|C|CAD|USD|GBP|EUR|AUD)?\s?[$£€]?\s?\d[\d,]*(?:\.\d+)?\s?[kK]?)?"
                 r"(?:\s?(?:CAD|USD|GBP|EUR|AUD|per year|/year|annually|/yr|per hour|/hour|/hr))?)")
YEARS = re.compile(r"(?<!after )(?<!within )(\d{1,2})\s?\+?\s?(?:-|–|to)?\s?(\d{1,2})?\+?\s*years?"
                   r"(?:[’']s?)?(?=\s*(?:of|in|as|with|experience|exp\b|working|professional|hands|"
                   r"relevant|progressive|related|industry|post)\b(?! employment| service)"
                   r"|[^.\n]{0,60}experience)", re.I)
YEARS_AFTER = re.compile(r"experience\W{0,3}(?:required\W{0,3})?(?:minimum (?:of )?)?(\d{1,2})\s?\+?\s*years?",
                         re.I)
KEY_LINE = re.compile(r"\d\s?\+?\s?(?:-|–|to)?\s?\d?\+?\s*years?|[$£€]\s?\d|salary|compensation|pay range|"
                      r"base pay|hourly|per hour|remote|hybrid|in[- ]office|on[- ]?site|days (?:a|per) week|"
                      r"qualifications|requirements|looking for|must have|you bring|you have|"
                      r"what you.ll need|about you|nice to have|asset", re.I)


def _amount(s):
    n = re.search(r"\d[\d,]*(?:\.\d+)?", s)
    v = float(n.group().replace(",", "")) if n else 0
    return v * 1000 if re.search(r"\d\s?[kK]", s) else v


def salary_hints(text):
    """Pay ranges only: drops perks like '$650 home office budget'."""
    out = []
    for h in SAL.findall(text or ""):
        h = h.strip()
        hourly = re.search(r"hour|/hr", h, re.I)
        if (hourly and _amount(h) >= 15) or _amount(h) >= 30000:
            out.append(h)
    return list(dict.fromkeys(out))[:4]


def salary_range(hints):
    """(low, high) annual numbers from the first usable hint; hourly x 1,950."""
    for h in hints or []:
        nums = [float(x.replace(",", "")) * (1000 if k else 1)
                for x, k in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s?([kK])?", h)]
        nums = [n for n in nums if n >= 15]
        if not nums:
            continue
        if re.search(r"hour|/hr", h, re.I) or max(nums) < 500:
            nums = [n * 1950 for n in nums]
        return min(nums), max(nums)
    return None


def years_hint(text):
    nums = [int(a) for a, b in YEARS.findall(text or "") if a and int(a) < 16]
    nums += [int(a) for a in YEARS_AFTER.findall(text or "") if int(a) < 16]
    return max(nums) if nums else None


def years_lines(text):
    return [l.strip()[:200] for l in (text or "").split("\n") if YEARS.search(l) or YEARS_AFTER.search(l)][:5]


def excerpt(text, head=1500, limit=5000):
    """Opening of the posting plus every line about years, pay, work mode or requirements."""
    if len(text) <= limit:
        return text
    keep = [l.strip() for l in text[head:].split("\n") if KEY_LINE.search(l)]
    return (text[:head] + "\n[...]\n" + "\n".join(dict.fromkeys(keep)))[:limit]


def iso_date(v):
    if v in (None, ""):
        return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v / 1000, tz=timezone.utc).astimezone().date().isoformat()
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return (d.astimezone() if d.tzinfo else d).date().isoformat()
    except Exception:  # noqa: BLE001
        return str(v)[:10]


# ---------------------------------------------------------------- fetchers
def f_greenhouse(slug, **_):
    r = S.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", timeout=T)
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        offices = "; ".join(o.get("name", "") + " " + (o.get("location") or "") for o in j.get("offices", []))
        yield dict(id=str(j["id"]), title=j["title"], url=j["absolute_url"],
                   location=f"{(j.get('location') or {}).get('name', '')}; {offices}", workplace="",
                   posted=iso_date(j.get("first_published") or j.get("updated_at")),
                   salary="", desc=clean(j.get("content")))


def f_lever(slug, **_):
    r = None
    for host in ("api.lever.co", "api.eu.lever.co"):
        r = S.get(f"https://{host}/v0/postings/{slug}?mode=json", timeout=T)
        if r.ok and isinstance(r.json(), list):
            break
    r.raise_for_status()
    for j in r.json():
        c = j.get("categories", {})
        sr = j.get("salaryRange") or {}
        sal = f"{sr.get('currency', '')} {sr.get('min')}-{sr.get('max')} {sr.get('interval', '')}" if sr else ""
        lists = " ".join(f"{l.get('text', '')}: {clean(l.get('content'))}" for l in j.get("lists", []))
        yield dict(id=j["id"], title=j["text"], url=j["hostedUrl"],
                   location="; ".join([c.get("location", "")] + (c.get("allLocations") or [])),
                   workplace=j.get("workplaceType", ""), posted=iso_date(j.get("createdAt")),
                   salary=sal, desc=clean(j.get("descriptionPlain", "") + "\n" + lists))


def f_ashby(slug, **_):
    r = S.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true", timeout=T)
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations", [])]
        addr = ((j.get("address") or {}).get("postalAddress") or {})
        comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
        yield dict(id=j["id"], title=j["title"], url=j["jobUrl"],
                   location="; ".join(locs + [addr.get("addressCountry", "")]),
                   workplace=("Remote" if j.get("isRemote") else "") + " " + (j.get("workplaceType") or ""),
                   posted=iso_date(j.get("publishedAt")), salary=comp,
                   desc=clean(j.get("descriptionPlain") or j.get("descriptionHtml")))


def f_workable(slug, **_):
    r = S.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true", timeout=T)
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        locs = "; ".join(f"{l.get('city', '')}, {l.get('region', '')}, {l.get('country', '')}"
                         for l in j.get("locations", []))
        yield dict(id=j["shortcode"], title=j["title"], url=j["url"], location=locs,
                   workplace="Remote" if str(j.get("telecommuting")).lower() == "true" else "",
                   posted=iso_date(j.get("published_on")), salary="", desc=clean(j.get("description")))


def f_smartrecruiters(slug, **_):
    off = 0
    while True:
        r = S.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={off}", timeout=T)
        r.raise_for_status()
        js = r.json()
        for j in js.get("content", []):
            l = j.get("location", {})
            wp = "Remote" if l.get("remote") else "Hybrid" if l.get("hybrid") else ""
            yield dict(id=j["id"], title=j["name"], url=f"https://jobs.smartrecruiters.com/{slug}/{j['id']}",
                       location=l.get("fullLocation", ""), workplace=wp,
                       posted=iso_date(j.get("releasedDate")), salary="", desc="",
                       _detail=f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{j['id']}")
        off += 100
        if off >= js.get("totalFound", 0) or off > 1000:
            break


def f_rippling(slug, **_):
    r = S.get(f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs", timeout=T)
    r.raise_for_status()
    for j in r.json():
        yield dict(id=j["uuid"], title=j["name"], url=j["url"],
                   location=(j.get("workLocation") or {}).get("label", ""), workplace="",
                   posted=None, salary="", desc="")


def f_pinpoint(slug, **_):
    r = S.get(f"https://{slug}.pinpointhq.com/postings.json", timeout=T)
    r.raise_for_status()
    for j in r.json().get("data", []):
        loc = j.get("location") or {}
        sal = ""
        if j.get("compensation_visible") and j.get("compensation_minimum"):
            sal = f"{j.get('compensation_currency')} {j['compensation_minimum']}-{j.get('compensation_maximum')}"
        yield dict(id=str(j["id"]), title=j["title"], url=j.get("url", ""),
                   location=f"{loc.get('city', '')}, {loc.get('province', '')}, {loc.get('country', '')}",
                   workplace=j.get("workplace_type", "") or "", posted=None, salary=sal,
                   desc=clean(j.get("description")))


def f_bamboohr(slug, **_):
    r = S.get(f"https://{slug}.bamboohr.com/careers/list", timeout=T)
    r.raise_for_status()
    for j in r.json().get("result", []):
        loc = j.get("location") or {}
        yield dict(id=str(j["id"]), title=j["jobOpeningName"], url=f"https://{slug}.bamboohr.com/careers/{j['id']}",
                   location=f"{loc.get('city', '')}, {loc.get('state', '')}",
                   workplace="Remote" if j.get("isRemote") else "", posted=None, salary="", desc="")


def wd_posted(text, today):
    t = (text or "").lower()
    if "today" in t:
        return today.isoformat()
    if "yesterday" in t:
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+? days? ago", t)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat() + ("~" if "+" in t else "")
    return None


def f_workday(slug, today=None, cutoff=None, **_):
    """An empty search comes back roughly newest-first: page until five pages in a row have
    nothing inside the window."""
    tenant, wd, site = slug.split("|")
    base = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
    seen, stale_pages = {}, 0
    for off in range(0, 1000, 20):
        r = S.post(f"{base}/jobs", json={"limit": 20, "offset": off, "searchText": "", "appliedFacets": {}},
                   timeout=T)
        r.raise_for_status()
        posts = r.json().get("jobPostings", [])
        if not posts:
            break
        fresh = 0
        for p in posts:
            d = (wd_posted(p.get("postedOn"), today) or "").rstrip("~")
            if d and cutoff and d >= cutoff.isoformat():
                fresh += 1
            path = p.get("externalPath", "")
            if path and path not in seen:
                seen[path] = p
        stale_pages = 0 if fresh else stale_pages + 1
        if stale_pages >= 5 or len(posts) < 20:
            break
    for path, p in seen.items():
        yield dict(id=path, title=p.get("title", ""), url=f"https://{tenant}.{wd}.myworkdayjobs.com/{site}{path}",
                   location=p.get("locationsText", ""), workplace="",
                   posted=wd_posted(p.get("postedOn"), today), salary="", desc="",
                   _detail=f"{base}{path}")


FETCHERS = dict(greenhouse=f_greenhouse, lever=f_lever, ashby=f_ashby, workable=f_workable,
                smartrecruiters=f_smartrecruiters, rippling=f_rippling, pinpoint=f_pinpoint,
                bamboohr=f_bamboohr, workday=f_workday)


def detail(job):
    """Fill in description/location for feeds whose list endpoint is thin (Workday, SmartRecruiters)."""
    try:
        js = S.get(job["_detail"], timeout=T).json()
        if "jobPostingInfo" in js:
            i = js["jobPostingInfo"]
            locs = [i.get("location", "")] + (i.get("additionalLocations") or [])
            job["location"] = "; ".join(l for l in locs if l) or job["location"]
            job["workplace"] = i.get("remoteType", "") or job["workplace"]
            job["desc"] = clean(i.get("jobDescription"))
            if i.get("startDate"):
                job["posted"] = iso_date(i["startDate"]) or job["posted"]
        elif "jobAd" in js:
            secs = js["jobAd"].get("sections", {})
            job["desc"] = clean(" ".join((v or {}).get("text", "") for v in secs.values()))
    except Exception as e:  # noqa: BLE001
        job["detail_error"] = str(e)[:120]
    return job
