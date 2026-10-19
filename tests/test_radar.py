from jhq.radar import feeds
from jhq.radar.companies import parse_link
from jhq.radar.filters import Prefs, rules_fit

PREFS = Prefs({
    "titles_include": ["analyst", "\\bBI\\b", "business intelligence"],
    "titles_exclude": ["intern", "director", "security"],
    "areas": [{"label": "Chicago area", "match": ["chicago", "evanston"], "modes": ["remote", "hybrid"]}],
    "country": "United States", "remote_in_country": True, "remote_global": "flag",
    "salary": {"floor": 85000, "use_midpoint": True}, "years_max": 5,
})


def test_titles():
    assert PREFS.title_ok("Senior Data Analyst")
    assert PREFS.title_ok("BI Developer")
    assert not PREFS.title_ok("Security Analyst")
    assert not PREFS.title_ok("Analytics Intern")
    assert not PREFS.title_ok("Software Engineer")
    assert not PREFS.title_ok("Ambiguous")  # "bi" inside a word doesn't count


def test_locations():
    assert PREFS.classify("Chicago, IL", "Hybrid")[0]
    assert not PREFS.classify("Chicago, IL - On-site", "")[0]
    keep, label, flags = PREFS.classify("Chicago, IL", "")
    assert keep and flags  # mode unclear: kept, flagged
    assert PREFS.classify("Remote - United States", "")[0]
    assert not PREFS.classify("Austin, TX", "Hybrid")[0]  # in country, not in an area
    assert not PREFS.classify("Remote - Canada", "")[0]  # remote, other country only
    assert not PREFS.classify("London, UK", "Hybrid")[0]
    keep, label, flags = PREFS.classify("Remote - Worldwide", "")
    assert keep and flags


def test_canadian_user_sees_canada_remote_not_us_only():
    p = Prefs({"areas": [{"label": "Toronto", "match": ["toronto"], "modes": ["remote", "hybrid"]}],
               "country": "Canada"})
    assert p.classify("Remote, Canada", "")[0]
    assert p.classify("Toronto, ON", "hybrid")[0]
    assert not p.classify("Remote - US", "")[0]


def test_pay_and_years_hints():
    text = "We need 3+ years of experience in SQL. Salary: $90,000 - $110,000 per year. $500 home office stipend."
    assert feeds.years_hint(text) == 3
    hints = feeds.salary_hints(text)
    assert hints and "$500" not in " ".join(hints)
    lo, hi = feeds.salary_range(hints)
    assert (lo, hi) == (90000, 110000)
    assert feeds.salary_range(["$45 - $55 per hour"]) == (45 * 1950, 55 * 1950)
    assert feeds.years_hint("Founded 50 years ago. RRSP after 2 years of employment.") is None


def test_rules_fit_prefers_real_matches():
    import re
    skills = [("SQL", re.compile("sql", re.I)), ("Tableau", re.compile("tableau", re.I))]
    good = {"title": "Data Analyst", "desc": "SQL and Tableau daily", "years_hint": 3,
            "_pay": (90000, 110000), "location_label": "Remote United States"}
    bad = {"title": "Payroll Analyst", "desc": "Payroll processing", "years_hint": 8, "_pay": (50000, 60000)}
    assert rules_fit(good, PREFS, skills, ["Data Analyst"])[0] >= 8
    assert rules_fit(bad, PREFS, skills, ["Data Analyst"])[0] <= 3


def test_slug_validation_blocks_url_tricks():
    assert feeds.valid_slug("greenhouse", "gitlab")
    assert not feeds.valid_slug("greenhouse", "../evil")
    assert not feeds.valid_slug("lever", "a/b")
    assert not feeds.valid_slug("greenhouse", "x?y=1")
    assert feeds.valid_slug("workday", "acme|wd5|External")
    assert not feeds.valid_slug("workday", "acme|evil.com|x")


def test_parse_job_links():
    assert parse_link("https://job-boards.greenhouse.io/gitlab/jobs/12345")[:2] == ("greenhouse", "gitlab")
    assert parse_link("https://jobs.lever.co/plaid/abc-123")[:2] == ("lever", "plaid")
    assert parse_link("https://jobs.ashbyhq.com/notion/9f0e")[:2] == ("ashby", "notion")
    assert parse_link("https://acme.wd5.myworkdayjobs.com/en-US/External/job/Chicago/Analyst_R1")[:2] == \
        ("workday", "acme|wd5|External")
    assert parse_link("https://www.example.com/careers") is None
