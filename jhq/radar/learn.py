"""Learned preferences: dated scoring rules the weekly review writes and every radar run applies.

    jhq radar learn list
    jhq radar learn add "4 of 6 skips were 'Too senior' for roles asking 4+ yrs: cap their fit at 6"
    jhq radar learn remove 2          # by number from `list`

They live in radar/preferences.json under "learned" (newest last). Rules are about scoring only:
anything that changes WHICH jobs are fetched (titles, places, pay floor, companies) goes to the
user as a suggestion instead. The weekly review adds at most 5 a week and removes rules the
evidence no longer supports; the list is capped at 20.
"""
from __future__ import annotations

import argparse

from .. import config

MAX_RULES = 20


def load(paths):
    return list((config.prefs(paths) or {}).get("learned") or [])


def save(rules, paths):
    prefs = config.prefs(paths) or {}
    prefs["learned"] = rules[-MAX_RULES:]
    config.write_json(paths.prefs, prefs, indent=2)


def main(argv=None):
    config.utf8_console()
    ap = argparse.ArgumentParser(prog="jhq radar learn")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("add"); s.add_argument("rule")
    s = sub.add_parser("remove"); s.add_argument("number", type=int)
    a = ap.parse_args(argv)
    paths = config.Paths()
    rules = load(paths)
    if a.cmd == "add":
        text = " ".join(a.rule.split())[:400]
        if not text:
            raise SystemExit("Empty rule.")
        rules.append(f"{config.today().isoformat()}: {text}")
        save(rules, paths)
        print(f"added rule {len(load(paths))}: {rules[-1]}")
    elif a.cmd == "remove":
        if not 1 <= a.number <= len(rules):
            raise SystemExit(f"No rule {a.number}; there are {len(rules)}.")
        gone = rules.pop(a.number - 1)
        save(rules, paths)
        print(f"removed: {gone}")
    else:
        for i, r in enumerate(rules, 1):
            print(f"{i}. {r}")
        print(f"# {len(rules)} learned rule(s)")


if __name__ == "__main__":
    main()
