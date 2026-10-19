"""Turn radar/preferences.json into filters: which titles, which places, which work modes.

The title filter is deliberately broad; Claude (or the rules score) judges real fit later.
"""
from __future__ import annotations

import re

REMOTE = re.compile(r"remote|anywhere|distributed|work from home|\bwfh\b|virtual|telecommut", re.I)
HYBRID = re.compile(r"hybrid|flexible", re.I)
ONSITE = re.compile(r"on[- ]?site|in[- ]office|in person|onsite", re.I)
GLOBAL = re.compile(r"north america|americas|\bnamer\b|global|worldwide|anywhere|any location", re.I)

# Places that identify a country. Used to drop "Remote - <another country>" postings.
COUNTRIES = {
    "United States": r"united states|\busa\b|\bu\.s\.a?\b|\bus\b(?!\w)|alabama|alaska|arizona|arkansas|"
                     r"california|colorado|connecticut|delaware|florida|georgia(?!n)|hawaii|idaho|illinois|"
                     r"indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|"
                     r"minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|"
                     r"new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|"
                     r"rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|"
                     r"washington|wisconsin|wyoming|san francisco|seattle|boston|chicago|austin|denver|"
                     r"atlanta|los angeles|\bnyc\b|palo alto|dallas|miami",
    "Canada": r"canada|\bcanadian\b|ontario|quebec|qu[ée]bec|british columbia|alberta|manitoba|"
              r"saskatchewan|nova scotia|new brunswick|newfoundland|toronto|montr[ée]al|vancouver|"
              r"calgary|ottawa|edmonton|winnipeg|halifax|waterloo",
    "United Kingdom": r"united kingdom|\buk\b|england|scotland|wales|london|manchester|edinburgh",
    "Ireland": r"ireland|dublin",
    "Germany": r"germany|deutschland|berlin|munich|hamburg",
    "France": r"france|paris",
    "Netherlands": r"netherlands|amsterdam",
    "Spain": r"spain|madrid|barcelona",
    "Portugal": r"portugal|lisbon",
    "Poland": r"poland|warsaw|krakow",
    "India": r"india|bengaluru|bangalore|hyderabad|pune|noida|gurgaon|gurugram|chennai|mumbai|delhi",
    "Australia": r"australia|sydney|melbourne",
    "Singapore": r"singapore",
    "Japan": r"japan|tokyo",
    "Mexico": r"mexico",
    "Brazil": r"brazil|s[ãa]o paulo",
    "Philippines": r"philippines|manila",
    "Israel": r"israel|tel aviv",
    "Europe (region)": r"\beurope\b|\bemea\b|\beu\b",
    "Asia-Pacific (region)": r"\bapac\b",
    "Latin America (region)": r"\blatam\b",
}


def _rx(words):
    words = [w for w in (words or []) if w and w.strip()]
    if not words:
        return None
    return re.compile("|".join(w if w.startswith("(?") or "\\" in w else re.escape(w).replace(r"\ ", r"\s+")
                               for w in words), re.I)


class Prefs:
    def __init__(self, p: dict):
        self.raw = p
        self.include = _rx(p.get("titles_include"))
        self.exclude = _rx(p.get("titles_exclude"))
        self.areas = [{"label": a.get("label", "area"), "rx": _rx(a.get("match")),
                       "modes": {m.lower() for m in a.get("modes", ["remote", "hybrid"])}}
                      for a in p.get("areas", []) if a.get("match")]
        self.country = p.get("country") or ""
        self.country_rx = re.compile(COUNTRIES[self.country], re.I) if self.country in COUNTRIES else _rx([self.country])
        self.remote_in_country = p.get("remote_in_country", True)
        self.remote_global = p.get("remote_global", "flag")  # "flag" | "skip"
        sal = p.get("salary") or {}
        self.salary_floor = sal.get("floor")
        self.salary_currency = sal.get("currency", "")
        self.use_midpoint = sal.get("use_midpoint", True)
        self.years_max = p.get("years_max")
        self.window_days = int(p.get("window_days", 2))

    def title_ok(self, title: str) -> bool:
        if self.include and not self.include.search(title or ""):
            return False
        return not (self.exclude and self.exclude.search(title or ""))

    def mode_of(self, text: str, workplace: str = "") -> str:
        t, w = f"{text} {workplace}", (workplace or "").lower()
        if REMOTE.search(t) or w == "remote":
            return "remote"
        if HYBRID.search(t) or w == "hybrid":
            return "hybrid"
        if ONSITE.search(t) or w in ("onsite", "on-site", "in office"):
            return "on-site"
        return "unclear"

    def other_country(self, text: str):
        for name, pat in COUNTRIES.items():
            if name == self.country:
                continue
            if re.search(pat, text, re.I):
                return name
        return None

    def classify(self, location: str, workplace: str = ""):
        """(keep, label, flags) for a posting's location text."""
        t = f"{location} {workplace}".strip()
        mode = self.mode_of(location, workplace)
        flags = []
        for a in self.areas:
            if a["rx"] and a["rx"].search(t):
                if mode == "unclear":
                    flags.append("work mode not stated: check")
                    return True, f"{a['label']} (mode unclear)", flags
                if mode in a["modes"]:
                    return True, f"{a['label']} ({mode})", flags
                return False, f"{a['label']} {mode}", flags
        in_country = bool(self.country_rx and self.country_rx.search(t))
        if in_country:
            if mode == "remote" and self.remote_in_country:
                return True, f"Remote {self.country}", flags
            return False, f"{self.country}, outside your areas ({mode})", flags
        if mode == "remote":
            other = self.other_country(t)
            if GLOBAL.search(t) and self.remote_global != "skip":
                flags.append(f"remote, region-wide: confirm you can be hired from {self.country or 'your country'}")
                return True, "Remote (region/global)", flags
            if other:
                return False, f"remote, {other} only", flags
            if self.remote_global != "skip":
                flags.append("remote, country not stated: confirm eligibility")
                return True, "Remote (country unclear)", flags
        return False, "outside your locations", flags

    def pay_check(self, low_high):
        """None when unknown, else (ok, value_used)."""
        if not low_high or not self.salary_floor:
            return None
        lo, hi = low_high
        v = (lo + hi) / 2 if self.use_midpoint else hi
        return v >= self.salary_floor, v


def rules_fit(job: dict, prefs: Prefs, skill_rx: list, target_titles=()) -> tuple[int, list[str], list[str]]:
    """A transparent 1-10 estimate used when Claude hasn't judged the lead yet."""
    why, gaps = [], []
    score = 4.0
    title = (job.get("title") or "").lower()
    text = f"{job.get('title', '')}\n{job.get('desc', '')}"
    if any(t and t.lower() in title for t in target_titles):
        score += 1.5
        why.append("one of your target titles")
    hits = [name for name, rx in skill_rx if rx.search(text)]
    if hits:
        score += min(3, 0.5 + len(hits) / 2)
        why.append("mentions your skills: " + ", ".join(hits[:6]))
    else:
        gaps.append("doesn't mention your main skills")
    yrs = job.get("years_hint")
    if yrs is not None and prefs.years_max is not None:
        if yrs > prefs.years_max:
            score -= 3
            gaps.append(f"asks {yrs}+ years (your max {prefs.years_max})")
        else:
            score += 1
            why.append(f"asks {yrs} years")
    pay = prefs.pay_check(job.get("_pay"))
    if pay is not None:
        ok, v = pay
        if ok:
            score += 1
            why.append(f"pay clears your floor (~{int(v):,})")
        else:
            score -= 3
            gaps.append(f"pay below your floor (~{int(v):,})")
    if "remote" in (job.get("location_label") or "").lower():
        score += 0.5
    return max(1, min(10, round(score))), why, gaps
