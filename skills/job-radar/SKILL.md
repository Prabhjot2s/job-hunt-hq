---
name: job-radar
description: Job Hunt HQ's job radar. Finds fresh postings (today and yesterday) on the user's watched companies' career sites, plus optional Indeed/Dice connectors and job-alert emails, judges each against the user's facts and preferences, verifies pay/years/work mode from the full posting, and saves scored leads to the dashboard's Jobs tab. Also syncs "Applied" clicks into the tracker, checks email for interview invites and rejections (optional Gmail connector), runs the weekly review that learns from skips and likes, and discovers new companies to watch. TRIGGER on "run my job radar", "find me jobs", "any new jobs today", "review my leads", "find companies for my radar", "add/remove a company", "weekly review", or when a scheduled task asks for the daily radar.
---

# Job radar

**Tool command:** `{{JHQ}}` (Bash tool; in PowerShell put `& ` in front). Paths: `{{JHQ}} where`.
Read-only toward the outside world: never apply, submit forms, or send/reply/label/delete email.
Keep token use low: the scripts fetch and filter; you judge.

Before judging anything read `<data>/radar/preferences.json`, `<data>/profile/facts.md` and
`<data>/profile/profile.json`. The full playbook is `references/playbook.md`.

## Daily run (in order)
1. **Housekeeping:** `{{JHQ}} radar sync` (copies dashboard "Applied" clicks into the tracker; harmless
   when there's nothing). `{{JHQ}} leads feedback` and use it when scoring today (many "Too senior"
   skips = score high-years roles lower; liked remote startups = score similar ones higher).
2. **Email outcomes (only if the Gmail connector is connected):** follow job-hunt Workflow E. For an
   interview invite on a tracked application, build the prep pack (job-hunt Workflow F, no questions).
3. **Company feeds:** `{{JHQ}} radar run`. Read the candidates JSON it prints last. Each job has
   `years_hint`, `years_lines` (the real requirement sentences), `salary_hints`, `location_label`,
   `flags` and a `desc` excerpt. "★" flags mark the user's priority companies.
4. **Job boards (optional):** if Indeed or Dice job-search connectors are available, run the
   `search_queries` from preferences.json for their areas and "remote", postings from the last 1-2 days.
   De-duplicate against step 3 and `{{JHQ}} leads links`.
5. **Job-alert emails (optional, Gmail):** read LinkedIn/Indeed job-alert emails from the window. Never
   log in to or browse LinkedIn; find each role on the employer's own site ("<company> <title> careers")
   and read that.
6. **Judge** every candidate with the rules in `references/playbook.md` (hard drops first, then fit 1-10,
   verdict, why, gaps). Verify the best ones from the full posting: `{{JHQ}} jd <url>` (add
   `verified: true` only when pay, years and work mode are all known).
7. **Save:** write the kept leads to a JSON list and `{{JHQ}} leads add leads.json`. They appear on the
   dashboard's Jobs tab (http://127.0.0.1:8765).
8. **Summary** for the user: email outcomes first (interview invites need action), then counts, the top
   5 roles with links and one line each, priority-company matches, and any feed errors.

## Other requests
- **"Review my leads" / re-score rules-scored leads:** leads with `scored_by: rules` came from an
  automatic run. Judge them like step 6 and `{{JHQ}} leads update changes.json`.
- **Add/remove companies, find new ones:** `references/playbook.md` "Discovery".
- **Weekly review:** `references/playbook.md` "Weekly review".
- **Change preferences:** edit preferences.json with the user (or use job-hunt-setup step 6).
