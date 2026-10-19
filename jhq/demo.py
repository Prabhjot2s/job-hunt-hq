"""Try the dashboard with a fictional person's data, without setting anything up.

    jhq demo [--port 8797] [--dir PATH] [--no-open]

Builds a throwaway data folder for "Alex Sample" (made-up applications, outcomes, job leads and
skill-gap data) in a temp folder, then starts the dashboard on it. Your real config and data are
never touched.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import random
import shutil
import tempfile
from pathlib import Path

APPS = [  # company, title, family, arrangement, salary (min, max), days ago, outcome, tags
    ("Acme Analytics", "Data Analyst", "Business Intelligence", "Hybrid", (85000, 105000), 2, None, "SQL; Tableau; KPIs"),
    ("Globex", "BI Analyst", "Business Intelligence", "Remote", (90000, 110000), 4, "screen", "SQL; Dashboards"),
    ("Initech", "Reporting Analyst", "Business Intelligence", "Hybrid", (70000, 82000), 6, "rejected", "Excel; Reporting"),
    ("Umbrella Health", "Data Analyst, Operations", "Operations Analytics", "Hybrid", (80000, 95000), 8, None, "SQL; Operations"),
    ("Hooli", "Product Analyst", "Product / Data", "Remote", (105000, 125000), 9, "interview", "A/B testing; SQL; Product"),
    ("Stark Retail", "Merchandising Analyst", "Retail Analytics", "On-site", (65000, 78000), 12, "rejected", "Excel; Retail"),
    ("Wayne Logistics", "Supply Chain Analyst", "Operations Analytics", "Hybrid", (72000, 88000), 14, None, "Excel; Forecasting"),
    ("Soylent Foods", "Marketing Analyst", "Marketing Analytics", "Remote", (78000, 92000), 15, "screen", "A/B testing; Marketing"),
    ("Cyberdyne", "Analytics Engineer", "Product / Data", "Remote", (115000, 140000), 18, "rejected", "dbt; SQL"),
    ("Tyrell Corp", "Data Analyst II", "Business Intelligence", "Hybrid", (88000, 104000), 20, "final", "SQL; Tableau; Stakeholders"),
    ("Vandelay Imports", "Business Analyst", "Operations Analytics", "Hybrid", (75000, 90000), 23, None, "Requirements; Excel"),
    ("Pied Piper", "Growth Analyst", "Marketing Analytics", "Remote", (95000, 115000), 26, "no-response", "A/B testing; SQL"),
    ("Massive Dynamic", "Insights Analyst", "Business Intelligence", "Hybrid", (82000, 98000), 29, "rejected", "Tableau; Storytelling"),
    ("Oscorp", "Pricing Analyst", "Commercial Analytics", "Hybrid", (90000, 108000), 33, "offer", "SQL; Pricing; A/B testing"),
    ("Aperture Labs", "Data Quality Analyst", "Business Intelligence", "Remote", (80000, 96000), 36, "no-response", "Data quality; Python"),
    ("Gringotts Bank", "Risk Data Analyst", "Commercial Analytics", "Hybrid", (92000, 112000), 40, "rejected", "SQL; Risk"),
]
LEADS = [
    (9, "Northwind Traders", "Senior Data Analyst", "Chicago, IL", "Hybrid", "$95,000 - $115,000", "3", True, "SQL, Tableau and A/B testing match your Northwind work; KPI ownership", "Looker preferred"),
    (8, "Contoso Cloud", "Business Intelligence Analyst", "Remote, United States", "Remote", "$100,000 - $120,000", "2-4", True, "Dashboards for sales leaders, SQL + Snowflake, same tools as you", "Salesforce data is new to you"),
    (8, "Fabrikam", "Analytics Analyst, Marketing", "Chicago, IL", "Hybrid", "$88,000 - $102,000", "3+", True, "Email A/B tests and promo analysis, exactly your Northwind projects", None),
    (7, "Litware", "Data Analyst", "Remote, United States", "Remote", "Not listed", "2+", False, "Retail data, SQL and Power BI", "Pay not listed"),
    (7, "Adventure Works", "Reporting Analyst", "Evanston, IL", "Hybrid", "$80,000 - $95,000", "2", True, "Replacing manual Excel reports with SQL", "More Excel-heavy than you'd like"),
    (6, "Proseware", "Product Data Analyst", "Remote, United States", "Remote", "$110,000 - $130,000", "4-5", True, "Experimentation and SQL", "Asks 4-5 years; product domain is new"),
    (5, "Tailspin Toys", "Analytics Engineer", "Chicago, IL", "Hybrid", "$120,000 - $140,000", "4+", False, "dbt and SQL", "Production dbt and Airflow ownership"),
]
EVENT_ORDER = {"screen": ["screen"], "interview": ["screen", "interview"], "final": ["screen", "interview", "final"],
               "offer": ["screen", "interview", "final", "offer"], "rejected": ["rejected"], "no-response": ["no-response"]}
JD_SKILLS = ["SQL", "Tableau", "Excel", "Python", "dbt", "Looker", "Power BI", "A/B testing", "stakeholders",
             "KPIs", "Snowflake", "forecasting", "Salesforce", "data quality", "dashboards", "statistics"]


def build(root: Path):
    from . import cli, config
    from . import tracker as trk
    from .build_package import build_jd

    os.environ["JHQ_HOME"] = str(root / "home")
    os.environ["JHQ_NO_SYNC"] = "1"
    alex = config.APP_DIR / "examples" / "alex-sample"
    cli.cmd_init(["--data-dir", str(root / "data"), "--port", "8797"])
    p = config.Paths()
    shutil.copy(alex / "profile.json", p.profile)
    shutil.copy(alex / "facts.md", p.facts)
    prefs = config.read_json(p.prefs)
    prefs.update(salary={"currency": "USD", "floor": 85000, "use_midpoint": True}, years_max=5, country="United States")
    config.write_json(p.prefs, prefs)
    tax = config.read_json(p.taxonomy)
    levels = {"SQL": "strong", "Excel (advanced)": "strong", "Tableau": "strong", "Data visualization / dashboards": "strong",
              "KPIs / metrics definition": "strong", "Stakeholder management": "strong", "Python": "working",
              "Power BI / DAX": "working", "A/B testing / experimentation": "working", "Snowflake": "working",
              "Data quality / validation": "working", "dbt": "project", "Forecasting": "project", "Statistics": "working"}
    for s in tax["skills"]:
        s["level"] = levels.get(s["skill"], s["level"])
    config.write_json(p.taxonomy, tax)

    rnd = random.Random(7)
    today = config.today()
    rows = []
    for co, title, fam, arr, (lo, hi), ago, outcome, tags in APPS:
        a_lo = round(rnd.uniform(0.72, 0.86), 2)
        c_lo = round(rnd.uniform(0.08, 0.2), 2)
        rows.append({"Company": co, "Job Title": title, "Date Applied": (today - dt.timedelta(days=ago)).isoformat(),
                     "Location": "Chicago, IL" if arr != "Remote" else "Remote, United States", "Work Arrangement": arr,
                     "Salary Range": f"${lo:,} - ${hi:,}", "Salary Min": lo, "Salary Max": hi, "Currency": "USD",
                     "Job Family": fam, "ATS Match When Applied": f"{int(a_lo * 100)}-{int(a_lo * 100) + 7}%",
                     "Callback Estimate": f"{int(c_lo * 100)}-{int(c_lo * 100) + 6}%", "ATS Low": a_lo,
                     "ATS High": a_lo + 0.07, "Callback Low": c_lo, "Callback High": c_lo + 0.06,
                     "Keyword Coverage": round(rnd.uniform(0.7, 0.95), 2), "Tailoring Level": rnd.choice(["High", "Medium"]),
                     "Cover Letter": rnd.choice(["Yes", "No"]), "Emphasis": tags,
                     "Direct Domain Experience": rnd.choice(["Yes", "Adjacent", "No"]),
                     "Main Strengths": "SQL and dashboards daily; KPI definition", "Main Gaps": "Domain is new",
                     "Resume Strategy": "Lead with dashboards and SQL automation."})
    trk.add(rows, p)
    for i, (*_, ago, outcome, _tags) in enumerate(APPS, 1):
        for k, ev in enumerate(EVENT_ORDER.get(outcome, [])):
            day = today - dt.timedelta(days=max(0, ago - 5 - 4 * k))
            trk.event(f"APP-{i:03d}", ev, date=day.isoformat(), paths=p)

    for co, title, *_ in APPS:
        folder = p.applications / config.safe_name(f"{co} - {title}")
        folder.mkdir(parents=True, exist_ok=True)
        picks = rnd.sample(JD_SKILLS, 7)
        txt = folder / "jd.txt"
        txt.write_text(f"{co} is hiring a {title}.\nYou bring: " + ", ".join(picks) + ".\n", encoding="utf-8")
        build_jd({"summary": [["Company", co], ["Job title", title]], "text_file": str(txt)},
                 f"{co} - {title}", folder / "Job Description.docx", folder)
        txt.unlink()
        config.write_json(folder / "tracker_meta.json", {"company": co, "title": title})
    from . import skill_gap
    config.write_json(p.skillgap, skill_gap.analyse(p))

    from .radar.leads import add_leads, normalise
    leads = []
    for fit, co, title, loc, mode, sal, yrs, ver, why, gaps in LEADS:
        rec = normalise({"fit": fit, "verdict": "Strong" if fit >= 8 else "Good" if fit >= 6 else "Stretch",
                         "company": co, "title": title, "location": loc, "work_mode": mode, "salary": sal,
                         "currency": "USD" if "$" in sal else None, "years": yrs,
                         "posted": (today - dt.timedelta(days=rnd.choice([0, 0, 1]))).isoformat(),
                         "source": "greenhouse feed", "link": f"https://example.com/jobs/{co.lower().replace(' ', '-')}",
                         "why": why, "gaps": gaps, "verified": ver,
                         "flags": ["★ DREAM: top choice"] if co == "Northwind Traders" else []})
        leads.append(rec)
    add_leads(leads, p)
    config.write_json(p.review, {"week": (today - dt.timedelta(days=today.weekday())).isoformat(),
                                 "summary": "16 applications in 6 weeks, 6 callbacks. Remote and hybrid roles with "
                                            "Tableau in the posting got most of your replies.",
                                 "applied_changes": ["Scoring now favours postings that mention A/B testing."],
                                 "suggestions": ["Add 'merchandising' to excluded titles? You skipped 4 of them."]})
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jhq demo")
    ap.add_argument("--port", type=int, default=8797)
    ap.add_argument("--dir")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.dir) if a.dir else Path(tempfile.mkdtemp(prefix="jhq-demo-"))
    marker = root / ".jhq-demo"
    if root.exists() and any(root.iterdir()):
        if not marker.exists():
            raise SystemExit(f"{root} isn't empty and isn't an old demo folder; pick another --dir.")
        shutil.rmtree(root / "data", ignore_errors=True)
        shutil.rmtree(root / "home", ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text("Job Hunt HQ demo data (fictional). Safe to delete.\n", encoding="utf-8")
    p = build(root)
    print(f"Demo data (fictional) in {p.root}")
    if a.build_only:
        return
    from .dashboard import server
    server.main(["--port", str(a.port)] + ([] if a.no_open else ["--open"]))
