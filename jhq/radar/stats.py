"""How the radar has been doing: volume per run and job feeds that keep failing.

    jhq radar stats [--last 7]

Reads the newest radar/runs/candidates_*.json files. A company whose feed failed in 3 or more of
those runs usually changed its job board: check it with `jhq companies find <website>` and fix the
slug, or remove it.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

from .. import config


def stats(paths, last=7):
    files = sorted(paths.runs.glob("candidates_*.json"))[-last:]
    runs, fails = [], Counter()
    last_error = {}
    for f in files:
        d = config.read_json(f, {}) or {}
        s = d.get("stats", {})
        runs.append({"run": f.stem.replace("candidates_", ""), "companies": s.get("companies"),
                     "jobs_scanned": s.get("jobs_scanned"), "title_matches": s.get("title_match"),
                     "candidates": s.get("candidates"), "feed_errors": s.get("feed_errors"),
                     "dropped": s.get("dropped")})
        for e in d.get("errors", []):
            fails[e.get("company")] += 1
            last_error[e.get("company")] = e.get("error")
    broken = [{"company": c, "failed_runs": n, "last_error": last_error.get(c)}
              for c, n in fails.most_common() if n >= 3]
    return {"runs_read": len(files), "runs": runs, "broken_feeds": broken,
            "candidates_total": sum(r["candidates"] or 0 for r in runs)}


def main(argv=None):
    config.utf8_console()
    ap = argparse.ArgumentParser(prog="jhq radar stats")
    ap.add_argument("--last", type=int, default=7, help="how many recent runs to read")
    a = ap.parse_args(argv)
    print(json.dumps(stats(config.Paths(), a.last), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
