"""Read a whole job posting: years, pay and work mode from the full description.

    jhq jd <url> [<url> ...]        # compact summary per posting
    jhq jd --full <url>             # also the key lines (requirements, pay, work mode)
    jhq jd --text <url>             # the whole description, for Job Description.docx
    jhq jd --json <url> [...]

Reads the ATS JSON APIs directly (Workday, Greenhouse, Lever, Ashby, SmartRecruiters), else the
page's JSON-LD JobPosting, else the page text. "only N chars read" usually means a JavaScript
page: open it in a browser instead, or ask the user to paste the text.
Job boards that block scripts (Indeed, ZipRecruiter, LinkedIn) are not fetched: find the
employer's own posting ("<company> <title> careers") and run this on that URL instead.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import sys
from urllib.parse import parse_qs, urlparse

import requests

from .. import config
from .feeds import S, T, clean, excerpt, salary_hints, years_hint, years_lines

BLOCKED_HOSTS = ("linkedin.com", "indeed.", "ziprecruiter.", "glassdoor.")


def _public_host(host):
    """Refuse localhost / private-network URLs (a pasted link shouldn't reach your router)."""
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except (socket.gaierror, ValueError):
        return False


def _check_url(url):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname or not _public_host(u.hostname):
        raise ValueError(f"not a public web address: {url}")
    if any(b in u.hostname for b in BLOCKED_HOSTS):
        raise ValueError(f"{u.hostname} blocks scripts; find the employer's own posting instead")


def get(url, **kw):
    """GET that re-checks every redirect hop, so a link can't bounce into your local network."""
    for _ in range(6):
        _check_url(url)
        r = S.get(url, timeout=T, allow_redirects=False, **kw)
        if r.is_redirect and r.headers.get("Location"):
            url = requests.compat.urljoin(url, r.headers["Location"])
            continue
        return r
    raise ValueError("too many redirects")


def workday(u):
    m = re.match(r"https://([^.]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)(/job/.+)", u)
    if not m:
        return None
    tenant, wd, site, path = m.groups()
    i = get(f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}{path}").json()["jobPostingInfo"]
    return dict(title=i.get("title"), company=tenant,
                location="; ".join([i.get("location", "")] + (i.get("additionalLocations") or [])),
                mode=i.get("remoteType", ""), text=clean(i.get("jobDescription")))


def greenhouse(u):
    m = re.search(r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?&]+)(?:/jobs/|.*?token=)(\d+)", u)
    q = parse_qs(urlparse(u).query)
    board = m.group(1) if m else (q.get("for") or [None])[0]
    jid = m.group(2) if m else (q.get("gh_jid") or q.get("token") or [None])[0]
    if not (board and jid):
        return None
    j = get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}").json()
    return dict(title=j.get("title"), company=board, location=(j.get("location") or {}).get("name", ""),
                mode="", text=clean(j.get("content")))


def lever(u):
    m = re.search(r"jobs\.(?:eu\.)?lever\.co/([^/]+)/([0-9a-f-]{36})", u)
    if not m:
        return None
    j = get(f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}").json()
    lists = " ".join(f"{l.get('text', '')}: {clean(l.get('content'))}" for l in j.get("lists", []))
    return dict(title=j.get("text"), company=m.group(1), location=(j.get("categories") or {}).get("location", ""),
                mode=j.get("workplaceType", ""), text=clean(j.get("descriptionPlain", "") + "\n" + lists))


def ashby(u):
    m = re.search(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})", u)
    if not m:
        return None
    js = get(f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}?includeCompensation=true").json()
    j = next((x for x in js.get("jobs", []) if x.get("id") == m.group(2)), None)
    if not j:
        raise ValueError("posting not on the board any more (closed?)")
    comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
    return dict(title=j.get("title"), company=m.group(1), location=j.get("location", ""),
                mode=("Remote " if j.get("isRemote") else "") + (j.get("workplaceType") or ""),
                text=clean(j.get("descriptionPlain") or j.get("descriptionHtml")) + (f"\nCompensation: {comp}" if comp else ""))


def smartrecruiters(u):
    m = re.search(r"smartrecruiters\.com/([^/]+)/(\d+)", u)
    if not m:
        return None
    js = get(f"https://api.smartrecruiters.com/v1/companies/{m.group(1)}/postings/{m.group(2)}").json()
    secs = (js.get("jobAd") or {}).get("sections", {})
    return dict(title=js.get("name"), company=m.group(1), location=(js.get("location") or {}).get("fullLocation", ""),
                mode="", text=clean(" ".join((v or {}).get("text", "") for v in secs.values())))


def generic(url):
    r = get(url, headers={"Accept": "text/html"})
    r.raise_for_status()
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', r.text, re.S | re.I):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in (data if isinstance(data, list) else [data]):
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                loc = item.get("jobLocation") or {}
                loc = loc[0] if isinstance(loc, list) and loc else loc
                addr = (loc or {}).get("address") or {}
                return dict(title=item.get("title"),
                            company=(item.get("hiringOrganization") or {}).get("name", ""),
                            location=", ".join(str(addr.get(k, "")) for k in ("addressLocality", "addressRegion",
                                                                               "addressCountry") if addr.get(k)),
                            mode=item.get("jobLocationType", ""), text=clean(item.get("description")))
    return dict(title="", company="", location="", mode="", text=clean(r.text))


def fetch(url):
    for fn in (workday, greenhouse, lever, ashby, smartrecruiters):
        try:
            res = fn(url)
        except ValueError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"{fn.__name__}: {e} (a 404 usually means the posting closed)") from e
        if res:
            return res
    return generic(url)


def check(url):
    try:
        p = fetch(url)
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": str(e)[:300]}
    t = p["text"] or ""
    return {"url": url, "title": p["title"], "company": p["company"], "location": p["location"],
            "mode": p["mode"], "chars": len(t), "years_hint": years_hint(t), "years_lines": years_lines(t),
            "salary_hints": salary_hints(t), "excerpt": excerpt(t, 800, 2500), "text": t}


def main(argv=None):
    config.utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    full, as_json, text = "--full" in argv, "--json" in argv, "--text" in argv
    urls = [a for a in argv if not a.startswith("--")]
    if not urls:
        raise SystemExit(__doc__)
    out = [check(u) for u in urls]
    if as_json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return
    for r in out:
        if "error" in r:
            print(f"! {r['url']}\n  {r['error']}\n")
            continue
        if text:
            print(r["text"])
            continue
        warn = "  (only {} chars read: JavaScript page? open it in a browser)".format(r["chars"]) if r["chars"] < 600 else ""
        print(f"{r['title']} | {r['company']} | {r['location']} | {r['mode'] or 'mode not stated'}{warn}")
        print(f"  years: {r['years_hint']}  pay: {', '.join(r['salary_hints']) or 'not stated'}")
        for l in r["years_lines"]:
            print(f"    - {l}")
        if full:
            print("  ---\n  " + r["excerpt"].replace("\n", "\n  "))
        print()


if __name__ == "__main__":
    main()
