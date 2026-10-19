---
name: job-hunt
description: Job Hunt HQ, a truthful AI job-application system. Tailors resumes and cover letters from job descriptions (DOCX + PDF), runs a measured ATS check with keyword coverage, gives before/after ATS and callback estimates, records applications and outcomes in the user's tracker, builds interview prep packs and mock interviews, maintains a skill-gap heatmap and learning plan, helps with application-form answers and outreach drafts, and analyzes what is working. TRIGGER whenever the user pastes or links a job description, asks to tailor or review a resume, asks how well they match a job, asks for a cover letter, says they applied or submitted somewhere, reports a callback, interview, offer, rejection or ghosting, asks to age out old applications, has an interview or wants prep or a mock interview, asks about skill gaps or what to learn, or asks what is working in their job search.
---

# Job Hunt HQ

Everything here is **strictly truthful**: never invent employers, titles, dates, metrics, tools or
domain experience to win a keyword. If something isn't in the user's facts file and they haven't
confirmed it in chat, it doesn't go on paper.

**Tool command:** `{{JHQ}}` (Bash tool; in PowerShell put `& ` in front). `{{JHQ}} where` prints every
path. If it says the system isn't set up, use the job-hunt-setup skill first.

## Read first
| Before you... | Read |
|---|---|
| Tailor anything | `<data>/profile/facts.md`, `<data>/profile/rules.md`, `<data>/profile/profile.json`, and `references/resume-rules.md` |
| Write a cover letter | `references/cover-letter-rules.md` |
| Touch the tracker | `references/tracker.md` |
| Interview prep or mock interview | `references/interview-prep.md` + `<data>/profile/star-stories.md` |
| Forms, salary answers, outreach, fetching postings | `references/tips.md` |

The user's rules.md overrides the defaults in references/ when they disagree.

## Workflow A: Tailoring from job description(s)
1. **Get the posting verbatim.** Pasted text, or `{{JHQ}} jd --text <url>` (company ATS links). For
   pages it can't read, use a browser tool if available, else ask the user to paste it. Check the link
   matches the role being discussed. Several jobs at once: split them and handle them together.
2. **Extract per job:** company, title, location, work arrangement, salary, must-haves, nice-to-haves,
   years asked, domain, and the user's weak spots vs facts.md. Write the **ATS keyword list** once:
   `required` (8-15 terms the posting treats as must-haves, in its exact wording) and `preferred`, with
   honest `aka` synonyms (see `{{JHQ}} ats -h`).
3. **Baseline before building anything:**

   | Company | Job Title | Current ATS Match Estimate | Current Callback Estimate |
   |---|---|---:|---:|

   Ranges, not points (`62-70%`, `8-14%`). Anchor the ATS estimate on a measured run against their base
   resume: `{{JHQ}} ats "<data>/profile/base_resume.pdf" --keywords kw.json`, and show its coverage %.
   Estimates are judgement; say so.
4. **One consolidated question set** across all jobs, only for material gaps (a tool they might have,
   a missing metric, a transferable story). Never fill gaps with invented experience. If a skill isn't
   confirmed, ask; don't assume yes or no.
5. **Removal table** (what you'd drop for this job and why). Wait for approval unless rules.md says
   reordering/dropping is fine without asking.
6. **Tailor** in the job's language with real evidence from facts.md. Keep employers, titles, dates
   and numbers exactly. Follow rules.md (length, headline, titles).
7. **Cover letter** per `references/cover-letter-rules.md` when rules.md says every package, or when asked.
8. **Build:** write `spec.json` in a scratch folder (format: `{{JHQ}} build -h` shows the docstring;
   `{{APP_DIR}}/examples/alex-sample/spec_acme.json` is a full example) with `company`, `title`, `link`,
   `resume`, `jd` (summary + `text_file` with the verbatim posting), `ats`, optional `cover_letter`, and
   `tracker.fields` (your final estimates, see step 10). Then `{{JHQ}} build spec.json`.
   It refuses to overwrite existing files: pass `--overwrite` only for files you made in this session,
   or after the user agrees.
9. **QA loop:** open the rendered PNGs (paths in the report) and look at them. Fix every warning
   (page fill, bold count, links, forbidden text, ATS parse issues, cover-letter warnings) by changing
   the spec, rebuild with `--overwrite`, look again. For each `missing` or `skills only` required
   keyword: if it's true for them, work it into a bullet; if it's a real gap, leave it out and say so.
   Never stuff keywords.
10. **Recruiter 6-second skim (recommended):** get a fresh look, ideally from a separate agent that
    only sees the rendered page: does the name/headline land, do bullet openings (first 3-5 words) show
    results, is the summary 2-3 lines, 5+ real numbers, 4-6 bold results max, any off-track title?
    Present it as a table (| Item | Verdict | What a recruiter notices | Fix |), apply approved fixes.
11. **Finish:**

    | Company | Job Title | Measured Keyword Coverage | Updated ATS Estimate | Updated Callback Estimate |
    |---|---|---:|---:|---:|

    The estimate must agree with the measured coverage (explain any big difference). Give clickable
    paths to the resume PDF/DOCX, cover letter and Job Description.docx. The spec's `tracker.fields`
    must hold the FINAL estimates: if they changed, update the spec and run `{{JHQ}} build spec.json
    --qa-only`, which refreshes `tracker_meta.json` without rebuilding. That file is what the tracker
    uses when the user clicks "Applied" on the dashboard. Then ask exactly: **"Should I add this to your tracker?"**
    A yes means record it; if they haven't said they submitted it, confirm the date applied first. Never
    mark something applied that wasn't submitted.

**If the user edited a generated DOCX themselves:** edit that file in place instead of rebuilding from
the spec (rebuilding would wipe their edits). Back it up first, then re-export and QA with
`{{JHQ}} build spec.json --qa-only`.

## Workflow B: Tracker updates
Read `references/tracker.md`. Writes only through `{{JHQ}} tracker` (add / update / event / age). It
backs up before every write and refuses if Excel has the file open: ask the user to close it.
- "I applied to X": search first (`tracker search`), then `tracker add` with the job's facts and the
  final estimates from its tracker_meta.json. A repeat application is a new row.
- "X called / rejected / ghosted me": `tracker event <id> screen|interview|technical|panel|final|offer|rejected|no-response|withdrawn|on-hold [--date] [--note]`.
- Old applications: `tracker age --days N` shows candidates; apply with `--apply` only after the user
  says yes to that list.
Report what changed and the backup path.

## Workflow C: What's working?
Use `tracker list --json` and the rules in `references/tracker.md` (Analysis): pending is not failure,
sample sizes with every rate, under 5 outcomes = directional only, check confounders, correlation is
not causation. End with keep / stop / test next.

## Workflow D: Finding jobs
Use the job-radar skill ("run my job radar", "find companies", "review my leads").

## Workflow E: Email outcomes (optional, needs the Gmail connector)
Read-only. Search since the last check for employer replies (`("unfortunately" OR "not moving forward"
OR "other candidates" OR "position has been filled" OR interview OR "next steps" OR availability OR
assessment OR offer) newer_than:7d`). Read each body before classifying: "we received your application"
and "still reviewing" are not rejections. Match to tracker rows and record events. Applications missing
from the tracker: list them and ask before adding. Never reply, label, archive or delete.

## Workflow F: Interview prep
Follow `references/interview-prep.md`. Output: `Interview Prep - <Stage>.docx` in the job's folder via
`{{JHQ}} md2docx`. Mock interviews only when asked.

## Workflow G: Skill gaps and learning plan
`{{JHQ}} skillgap --print` reads every saved Job Description.docx and writes the heatmap data for the
dashboard's Skills tab. Levels in `<data>/profile/skill_taxonomy.json` are the user's confirmed levels:
change one only when they confirm new experience (and update facts.md too). For a learning plan: rerun
it, web-search current free resources for the top 3-5 gaps, give each a small proof project, skip gaps
that can't be learned alone, and save `<data>/skill-gap/Learning Plan.md` + `.docx` (md2docx). Label
any callback numbers "directional only".

## Always
- Never submit applications, send messages or emails, or fill forms unless the user explicitly asks
  for that one action.
- Ask only for material missing information; state low-risk assumptions.
- End with clickable paths to every file created or changed.
- New true facts that come up (a metric, a tool, a story): offer to add them to facts.md /
  star-stories.md; write only with the user's OK.

Credit: the measured ATS check, cover-letter rules, interview prep and skill-gap ideas are adapted from
MadsLorentzen/ai-job-search (MIT licence).
