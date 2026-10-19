"""Measured ATS check: read the resume PDF's text layer the way a parser does, then score it.

    jhq ats resume.pdf --keywords kw.json [--dump DIR] [--json]

Adapted from MadsLorentzen/ai-job-search (MIT), tools/verify_pdf.py. The tailoring workflow's
ATS *estimates* are judgement; this is the measured part.

kw.json (also accepted: the "ats" block of a build spec):
{"required": ["SQL", {"term": "stakeholder management", "aka": ["stakeholders"]}],
 "preferred": ["dbt"]}
A keyword is a string or {"term": ..., "aka": [...]}. "aka" lists honest synonyms; an aka
hit is partial credit, because many ATS keyword filters are literal.

Checks:
  1. Text extracted by two parsers (pymupdf, pypdf), with no (cid:NN) or U+FFFD garbage.
  2. Email and phone survive as plain text (a link alone is invisible to an ATS).
  3. Section headings appear in the visual order, each on its own line.
  4. Date ranges have a start and an end joined by an ASCII hyphen.
  5. Keyword coverage: where each keyword appears (experience / summary / projects / skills only)
     or missing. A keyword only in Skills is weaker than one used in a bullet.
Score: required = 2 points, preferred = 1. Full credit in summary/experience/projects,
0.75 when only in Skills, 0.5 when only an aka matches.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from . import config

SECTION_ORDER = ["SUMMARY", "PROFILE", "PROFESSIONAL SUMMARY", "PROFESSIONAL EXPERIENCE", "EXPERIENCE",
                 "WORK EXPERIENCE", "PERSONAL PROJECTS", "PROJECTS", "SKILLS", "TECHNICAL SKILLS",
                 "EDUCATION", "CERTIFICATIONS", "LANGUAGES", "VOLUNTEERING", "AWARDS", "PUBLICATIONS"]
FOLDS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                       "–": "-", "—": "-", " ": " ", "•": " ", "": " "})
NON_ASCII_DASHES = "‐‑‒–—―−"
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
DATE_RANGE = re.compile(rf"((?:{MONTH}\s+)?(?:19|20)\d\d)\s*([-{NON_ASCII_DASHES}]|to)\s*"
                        rf"((?:{MONTH}\s+)?(?:19|20)\d\d|Present|Current|Now)", re.I)


def fold(text):
    return " ".join(unicodedata.normalize("NFC", text).translate(FOLDS).split())


def extract(pdf):
    """{parser_name: raw_text} for every parser that works."""
    out = {}
    try:
        import pymupdf
        with pymupdf.open(str(pdf)) as d:
            out["pymupdf"] = "\n".join(p.get_text() for p in d)
    except Exception as e:  # noqa: BLE001
        out["pymupdf_error"] = str(e)
    try:
        from pypdf import PdfReader
        out["pypdf"] = "\n".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
    except Exception as e:  # noqa: BLE001
        out["pypdf_error"] = str(e)
    return out


def term_regex(term):
    """Case-insensitive, whitespace/hyphen tolerant, word-bounded, optional plural."""
    t = fold(term).lower()
    parts = [re.escape(p) for p in re.split(r"[\s\-/]+", t) if p]
    if len(parts[-1]) > 3 and parts[-1].endswith("s") and not parts[-1].endswith("ss"):
        parts[-1] = parts[-1][:-1]
    body = r"[\s\-/]*".join(parts)
    return re.compile(rf"(?<![a-z0-9]){body}(?:s|es)?(?![a-z0-9])", re.I)


def sections(lines):
    current, owner, found = "HEADER", [], []
    for ln in lines:
        s = ln.strip().upper()
        if s in SECTION_ORDER:
            current = s
            found.append(s)
        owner.append(current)
    return owner, found


def visual_headings(pdf):
    try:
        import pymupdf
    except ImportError:
        return None
    hits = []
    with pymupdf.open(str(pdf)) as d:
        for pno, page in enumerate(d):
            for b in page.get_text("blocks"):
                for ln in b[4].splitlines():
                    if ln.strip().upper() in SECTION_ORDER:
                        hits.append((pno, round(b[1], 1), ln.strip().upper()))
    return [h[2] for h in sorted(hits)]


def bucket(sec):
    if sec in ("SKILLS", "TECHNICAL SKILLS"):
        return "skills"
    if sec in ("SUMMARY", "PROFILE", "PROFESSIONAL SUMMARY", "HEADER"):
        return "summary"
    if sec in ("PERSONAL PROJECTS", "PROJECTS"):
        return "projects"
    if sec in ("PROFESSIONAL EXPERIENCE", "EXPERIENCE", "WORK EXPERIENCE"):
        return "experience"
    return "other"


def locate(rx, lines, owner):
    where = []
    for ln, sec in zip(lines, owner):
        if rx.search(fold(ln)):
            b = bucket(sec)
            if b not in where:
                where.append(b)
    return where


def norm_kw(k):
    return (k, []) if isinstance(k, str) else (k["term"], list(k.get("aka") or []))


def keyword_table(raw, keywords):
    lines = raw.replace("-\n", "-").splitlines()
    owner, _ = sections(lines)
    rows, got, total = [], 0.0, 0.0
    for prio, weight in (("required", 2), ("preferred", 1)):
        for k in keywords.get(prio, []):
            term, aka = norm_kw(k)
            where = locate(term_regex(term), lines, owner)
            aka_hit = next((a for a in aka if locate(term_regex(a), lines, owner)), None)
            if where and set(where) - {"skills", "other"}:
                status, credit = "covered", 1.0
            elif where:
                status, credit = "skills only", 0.75
            elif aka_hit:
                status, credit = f"synonym only ({aka_hit})", 0.5
            else:
                status, credit = "missing", 0.0
            total += weight
            got += weight * credit
            rows.append({"keyword": term, "priority": prio, "status": status, "where": where})
    return rows, round(100 * got / total, 1) if total else None


def check(pdf, keywords=None, dump_dir=None, prof=None):
    if prof is None:
        try:
            prof = config.profile()
        except SystemExit:
            prof = {}
    pdf = Path(pdf)
    texts = extract(pdf)
    parsers = [p for p in ("pymupdf", "pypdf") if p in texts]
    issues, rep = [], {"pdf": str(pdf), "parsers": parsers}
    if not parsers:
        return {**rep, "issues": ["no parser could read the PDF"], "passed": False, **texts}
    primary = texts[parsers[0]]

    for p in parsers:
        t = texts[p]
        if len(fold(t)) < 400:
            issues.append(f"{p}: only {len(fold(t))} characters extracted (image-only or broken text layer?)")
        if re.search(r"\(cid:\d+\)", t) or "�" in t:
            issues.append(f"{p}: garbage glyphs in the text layer ((cid:NN) or U+FFFD)")
        if dump_dir:
            Path(dump_dir).mkdir(parents=True, exist_ok=True)
            (Path(dump_dir) / f"ats_text_{p}.txt").write_text(t, encoding="utf-8")

    flat = fold(primary)
    if prof.get("email") and prof["email"].lower() not in flat.lower():
        issues.append("email is not in the text layer as plain text")
    digits = re.sub(r"\D", "", prof.get("phone") or "")
    if digits and digits[-7:] not in re.sub(r"\D", "", flat):
        issues.append("phone number is not in the text layer as plain text")

    _, found = sections(primary.splitlines())
    rep["sections_found"] = found
    visual = visual_headings(pdf)
    for p in parsers:
        got = sections(texts[p].splitlines())[1]
        if visual is not None and got != visual:
            issues.append(f"{p}: heading order {got} differs from the page {visual}")
    if not any(s in found for s in ("PROFESSIONAL EXPERIENCE", "EXPERIENCE", "WORK EXPERIENCE")):
        issues.append("no EXPERIENCE heading found on its own line")
    if "EDUCATION" not in found:
        issues.append("heading EDUCATION not found on its own line")

    ranges = DATE_RANGE.findall(primary)
    rep["date_ranges"] = [f"{a} {b} {c}" for a, b, c in ranges]
    for a, dash, c in ranges:
        if dash in NON_ASCII_DASHES:
            issues.append(f"date range uses U+{ord(dash):04X} instead of '-': {a} {dash} {c}")
    if not ranges:
        issues.append("no 'Mon YYYY - Mon YYYY/Present' date range found; an ATS may not read tenure")

    if keywords:
        tables = {p: keyword_table(texts[p], keywords) for p in parsers}
        rows, score = tables[parsers[0]]
        rep["keywords"] = rows
        rep["keyword_coverage_pct"] = score
        if len(parsers) > 1:
            other = {r["keyword"]: r["status"] for r in tables[parsers[1]][0]}
            diff = [r["keyword"] for r in rows
                    if (r["status"] == "missing") != (other.get(r["keyword"]) == "missing")]
            if diff:
                issues.append(f"parsers disagree on: {', '.join(diff)} (check line breaks/hyphenation)")
        rep["missing_required"] = [r["keyword"] for r in rows
                                   if r["priority"] == "required" and r["status"] == "missing"]

    rep["issues"] = issues
    rep["passed"] = not issues
    return rep


def print_table(rep):
    print(f"ATS check: {rep['pdf']}")
    print(f"Parsers: {', '.join(rep['parsers'])}  |  sections: {' > '.join(rep.get('sections_found', []))}")
    if rep.get("keywords"):
        print(f"\nKeyword coverage: {rep['keyword_coverage_pct']}%\n")
        print("| Keyword | Priority | Status | Where |")
        print("|---|---|---|---|")
        for r in rep["keywords"]:
            print(f"| {r['keyword']} | {r['priority']} | {r['status']} | {', '.join(r['where']) or '-'} |")
    print("\nParse issues: " + ("none" if not rep["issues"] else ""))
    for i in rep["issues"]:
        print(f"  - {i}")


def main(argv=None):
    config.utf8_console()
    ap = argparse.ArgumentParser(prog="jhq ats", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--keywords", help="JSON file: {required: [...], preferred: [...]} or a build spec")
    ap.add_argument("--dump", help="write each parser's raw text here")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    kw = None
    if a.keywords:
        kw = json.loads(Path(a.keywords).read_text(encoding="utf-8"))
        kw = kw.get("ats", kw)
    rep = check(a.pdf, kw, a.dump)
    if a.json:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        print_table(rep)
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
