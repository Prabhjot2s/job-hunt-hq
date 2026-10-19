# Radar playbook

## Judging a candidate

### Hard drops (don't save these at all)
Apply the user's preferences.json:
1. **Years:** the real requirement (from `years_lines` or the full posting, not the title) is above
   `years_max`. Titles alone ("Senior", "Lead") don't decide it.
2. **Pay:** a stated range whose midpoint (or top, if `use_midpoint` is false) is under `salary.floor`.
   Hourly x 1,950 = yearly. Watch the currency: convert only if the user asked for that.
3. **Work mode / place:** outside their `areas` and modes (e.g. on-site when they accept remote/hybrid
   only), or remote but only for another country.
4. **Eligibility:** visa, clearance, language or licence requirements they've said they can't meet.
5. Anything in preferences `notes` marked as a deal-breaker.
No pay or no years stated: keep it if it otherwise fits, but it is not verified.

### Fit score (1-10)
Compare the posting with facts.md (what they've really done), not with keywords alone:
- 9-10: they've done most of the core work, with the main tools, at about this level.
- 7-8: strong match with one real gap or a level stretch.
- 5-6: plausible, with a catch (domain, a must-have tool they lack, seniority).
- 1-4: stretch; save only if it's from a priority company.
Adjust with `leads feedback` (skip reasons and likes) and preferences `notes`. Verdict: Strong (8+),
Good (6-7), Stretch (5 or less).

### Lead fields (for `{{JHQ}} leads add`)
`fit`, `verdict`, `company`, `title`, `location`, `work_mode`, `salary` (as posted, or "Not listed"),
`currency`, `years` (number or text), `posted` (YYYY-MM-DD), `source` (e.g. "greenhouse feed",
"Indeed"), `link`, `careers` (from the candidate JSON), `why` (one line: the 2-3 strongest matches),
`gaps` (one line), `flags` (list: keep the candidate's flags, add e.g. "work mode unclear", "check
visa"), `role_family`, and `verified: true` only after reading the full posting with pay, years and
mode all known.

### Verified vs unverified
The dashboard puts only verified fit-8+ leads (and priority-company leads) under "Apply today".
Always try to verify the leads you'd recommend: `{{JHQ}} jd <url>` reads the whole posting.

## Discovery (finding companies to watch)
- From names or websites: `{{JHQ}} companies find acme.com "Globex" ...` finds the job board (HTML scan,
  then name guesses on Greenhouse/Lever/Ashby/Workable/SmartRecruiters) and shows open jobs and how many
  match the user's titles and places.
- From job links in web-search results: `{{JHQ}} companies link <url> ...` (shows the board and whether it's
  already watched).
- Good searches: `"<target title>" "<city>" site:boards.greenhouse.io` (also jobs.lever.co,
  jobs.ashbyhq.com, myworkdayjobs.com), "<industry> companies <city>", recent funding news in their
  field, "remote <title> <country>".
- Propose companies with matching roles as a table (company, board, open jobs, matches, why). Add the
  approved ones: `{{JHQ}} companies add new.json` (`[{"company","ats","slug","tier","priority","note"}]`).
  Remove with `{{JHQ}} companies remove "Name"`.
- Unsupported systems (iCIMS, Taleo, SuccessFactors, Oracle, Jobvite, Dayforce) can't be watched; use
  job-alert emails or the job-board connectors for those companies.

## Weekly review
1. `{{JHQ}} leads feedback --days 7` and `{{JHQ}} tracker stats`.
2. Look for patterns: skip reasons (too senior? low pay? wrong role?), liked leads, which companies
   produce nothing, which titles produce good leads, applications vs the daily goal.
3. Write `<data>/radar/weekly_review.json`:
   `{"week": "YYYY-MM-DD", "summary": "...", "applied_changes": [...], "suggestions": [...]}`.
   Small safe changes you made (e.g. scoring note added to preferences `notes`) go in
   `applied_changes`; anything that changes what they see (new exclude words, salary floor, removing
   companies) goes in `suggestions` for them to approve. The dashboard shows this card on the Jobs tab.
4. Run a short discovery sweep (5-10 new companies) and suggest them.

## Missed runs
`radar run` catches up automatically after the computer was off (up to a week). Widen the job-board and
email searches to the window it reports.
