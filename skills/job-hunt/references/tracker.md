# The tracker

`<data>/tracker/applications.xlsx`, sheet **Applications**, one row per application. Plain cells, no
formulas or charts (the dashboard does the maths). All writes go through `{{JHQ}} tracker`, which:
backs the file up to `tracker/backups/` first, refuses while Excel has it open, validates every value,
and prints what it wrote. Report the backup path to the user.

## Columns
| Column | Rules |
|---|---|
| Application ID | `APP-###`, assigned by the tool, never reused |
| Company, Job Title | Exact names. If the employer's confirmation email uses a different title than the posting, use the email's |
| Status | Applied, On Hold, Recruiter Screen, Interview, Final Interview, Offer, Rejected, No Response, Withdrawn |
| Date Applied | The real submission date. Never guessed from file dates. `today` is allowed |
| Status Updated | Date of the last change (events set it) |
| Outcome Stage | Application Submitted, Recruiter Screen, First Interview, Technical / Case, Panel Interview, Final Interview, Offer, Closed |
| Final Outcome | Pending, Callback, Interview, Offer, Rejected, No Response, Withdrawn |
| Priority | High, Normal, Low |
| Location, Work Arrangement | Arrangement: Remote, Hybrid, On-site, Flexible, - |
| Salary Range / Min / Max / Currency | Range as text; min/max as numbers (hourly is fine, the dashboard annualizes) |
| Contract Type | Permanent, Fixed-term, Contract, Temporary, Internship, - |
| Job Family, Industry | Free text; keep job families consistent so the dashboard can group them |
| ATS Match When Applied, Callback Estimate | Text ranges like `80-87%` (**protected**: recorded once, never revised) |
| ATS Low/High, Callback Low/High | Decimals (0.80) or percents ("80%") (**protected**) |
| Keyword Coverage | The measured coverage, filled from tracker_meta.json (**protected**) |
| Resume File | Path of the submitted PDF (**protected**) |
| Resume Pages, Cover Letter (Yes/No), Tailoring Level (High/Medium/Light) | |
| Emphasis | Tags for what the resume leaned on, separated by `;` (e.g. `SQL; Dashboards; Stakeholders`). Keep tag names consistent: the Insights tab compares them |
| Direct Domain Experience | Yes, Adjacent, Project-based, No |
| Main Strengths, Main Gaps | Job-specific |
| Resume Strategy | The positioning used (**protected**) |
| Job Source / URL | The posting link |
| Follow-Up / Callback / First Interview / Offer / Rejection Date | Dates |
| Notes | Free text; use `"Notes+"` in updates to append instead of replace |

## Commands
```bash
{{JHQ}} tracker search "acme"                       # always search before adding
{{JHQ}} tracker add rows.json                       # [{"Company": ..., "Job Title": ..., "Date Applied": "today", ...}]
{{JHQ}} tracker update updates.json                 # [{"id": "APP-004", "fields": {"Follow-Up Date": "2026-11-02", "Notes+": "..."}}]
{{JHQ}} tracker event APP-004 interview --date 2026-11-03 --note "Hiring manager, 45 min"
{{JHQ}} tracker age --days 30                       # list only; --apply after the user agrees
{{JHQ}} tracker list --json   |   jhq tracker stats
```
Protected columns can only change with `--allow-protected`, and only when the user asks for a correction.

## New application (only after the user says they submitted it)
1. `tracker search` by company and title. A repeat application is a **new** row.
2. Fill everything you can: job facts, the **final** estimates and Keyword Coverage (from the job
   folder's tracker_meta.json `fields`), Resume File, pages, cover letter, tailoring level, Emphasis tags,
   domain fit, strengths, gaps, strategy, link. Status defaults to Applied / Application Submitted /
   Pending.
3. Date: "today" / "just now" = `today`. No date given = ask (unless they allow a blank).
4. Report the APP ID and backup path.
(Leads marked "Applied" on the dashboard are added automatically by `{{JHQ}} radar sync`, which also uses
tracker_meta.json.)

## Events (status changes)
| User says | Command |
|---|---|
| recruiter reached out / screen booked | `event <id> screen` |
| interview (first) | `event <id> interview` (also `technical`, `panel`) |
| final round | `event <id> final` |
| offer | `event <id> offer` |
| rejected / position filled | `event <id> rejected` |
| no reply for a long time (user decides) | `event <id> no-response` or the `age` batch |
| they withdrew | `event <id> withdrawn` |
| paused | `event <id> on-hold` |
Use the date they give (`--date`); events never clear earlier callback/interview dates.

## Aging (no-response batch)
Eligible: Status Applied/On Hold, Final Outcome Pending, no callback/interview/offer/rejection date,
Date Applied older than the threshold. Rows without a Date Applied are listed separately: ask for dates.
Show the list, get a yes, then `--apply`.

## Analysis rules
- Pending is not failure: report it separately. Exclude Withdrawn from response rates.
- Give n with every rate. Under 5 outcomes in a group = directional only; prefer 10+.
- Segment when there's enough data: job family, industry, domain fit, work arrangement, salary band,
  ATS estimate band, keyword coverage, tailoring level, cover letter yes/no, emphasis tags, source.
- Compare the callback estimates with what actually happened (calibration).
- Check confounders (domain fit, missing must-have tools, location, seniority). Correlation is not
  causation. End with **keep / stop / test next**.
