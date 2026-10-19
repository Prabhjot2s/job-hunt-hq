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
Then apply every **learned rule** (`{{JHQ}} radar learn list`; they override the general guidance
above when they conflict) and preferences `notes`. Verdict: Strong (8+), Good (6-7), Stretch (5 or less).

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

## Weekly review (how the radar learns)
Run it once a week (setup offers a Sunday scheduled task) or when the user asks. Read-only toward the
world: never apply, never message anyone, never write to the tracker.

**1. Gather evidence**
- `{{JHQ}} leads feedback --days 7` and `--days 30`: every lead the user applied to, liked (with
  reasons) or skipped (with one-click reasons such as "Too senior", "Low pay", "On-site", "Wrong
  role"), plus high-fit leads they ignored (a sign of over-scoring).
- Outcomes, read-only: `{{JHQ}} tracker list --json`. Which job families, company types, work modes
  and pay bands got callbacks or interviews vs rejections or silence. Fewer than 5 outcomes in a group =
  directional only; say so.
- `{{JHQ}} radar stats --last 7`: leads volume per run and feeds that failed in 3+ runs.
- The current learned rules (`{{JHQ}} radar learn list`), preferences.json and `{{JHQ}} companies list`.

**2. Decide**
- **Apply yourself (scoring only, easy to undo), at most 5 changes a week:** add learned rules with
  `{{JHQ}} radar learn add "<evidence>: <rule>"`, written so the evidence is visible, e.g.
  "6 of 9 skips were 'Too senior' on roles asking 4+ yrs: cap those at fit 6" or "both likes and the only
  callback were remote ops roles: +1 fit for remote ops roles at 0-4 yrs". Remove rules the new evidence
  no longer supports (`{{JHQ}} radar learn remove <n>`); update a rule by removing and re-adding it.
- **Fix broken feeds** when the fix is only a new board name: re-find it with
  `{{JHQ}} companies find <website>`, then remove and re-add the company. List it as an applied change.
- **Suggest only (needs the user's yes):** anything that changes which jobs are fetched or how much
  work it creates: new or removed titles, areas or work modes, the pay floor, the years cap, the daily
  goal, the schedule, and adding or removing companies (for additions, run a short discovery sweep for
  companies like the ones they liked and include the verified board for each).
- **Skill gaps:** `{{JHQ}} skillgap --print`. If a new skill entered the top 5 gaps, or one moved by 5+
  gap points, add a suggestion ("Skill gap: <skill> now asked in X% of postings"). Never change skill
  levels; only the user's confirmed experience changes those.

**3. Report**
Write `<data>/radar/weekly_review.json` with Python (json, UTF-8):
`{"week": "<Monday's date>", "summary": "<2-3 sentences: volume, applications vs goal, top skip reasons, what's working>", "applied_changes": [...], "suggestions": [...]}`.
The dashboard's Jobs tab shows it as "What the radar learned". Finish with the same summary, the
changes made and the suggestions, so the user can answer yes or no to each.

## Missed runs
`radar run` catches up automatically after the computer was off (up to a week). Widen the job-board and
email searches to the window it reports.
