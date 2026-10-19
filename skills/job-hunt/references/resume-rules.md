# Resume rules (defaults)

The user's `profile/rules.md` overrides anything here. Their `facts.md` is the only source of facts.

## Truth
- Employers, job titles, dates, degrees and numbers are copied exactly from facts.md. Never round a
  number up, never stretch a date range, never upgrade a title.
- A tool or skill goes on the resume only if facts.md (or the user, in chat) confirms it. Unsure = ask.
- Depth matters: "used on one project" is not "expert". Put light skills in Skills, not in bullets.
- No leadership or ownership words the user can't defend ("Led", "Owned", "Spearheaded", "Mentored")
  unless facts.md supports them. Prefer "Built", "Ran", "Wrote", "Worked with", "Cut", "Designed".
- If the job asks for something they don't have, leave it out and name the gap honestly in your
  summary to them (and, if useful, in the cover letter with the nearest real experience).
- Every phrase must survive "tell me more about that" in an interview.

## Content
- **Summary:** 2-3 lines. Who they are (their real title), years (as rules.md states them), 2-3 strengths
  that match this job, in the job's words.
- **Bullets:** start with the result or the action, not "Responsible for". About 1-1.5 lines each.
  Put the number first when there is one ("Cut reporting time from 6 hours to 1 by ..."). Don't repeat
  the same phrase across bullets.
- **Relevance beats volume:** if the job doesn't care about something, drop it. A tight page wins.
- **Skills:** grouped lines with a bold label ("**Analytics:** SQL, Excel, ..."). Only the label is
  bold. Order by what the job asks for.
- **Projects:** only when they support this job. Link the project name itself: `[Name](https://url)`
  (the build turns it into a real hyperlink and QA checks it survives into the PDF). Don't also print
  the URL.
- **Headline** under the name (optional): at most 3 items, e.g. "Data Analyst | SQL | Tableau".

## Format (what the builder enforces or checks)
- One clean column, standard section names (SUMMARY, PROFESSIONAL EXPERIENCE, SKILLS, EDUCATION,
  CERTIFICATIONS, PROJECTS) so ATS parsers find them. No tables, text boxes or images.
- Dates as `Mon YYYY - Mon YYYY` or `- Present`, with a plain hyphen.
- Phone and email as plain text in the header (links alone are invisible to an ATS).
- Bold: about 10 fragments max across summary and experience, on results and key terms only.
- Length: one page that is nearly full (QA warns under the `page_fill_min` in profile.json), or a
  second page that is at least half full. Never a few orphan lines on page 2.
- To fit: adjust `sizes` in the spec in small steps (0.1-0.2 pt), then spacing, then trim the weakest
  bullet. To fill: grow sizes slightly or add a relevant, true bullet. Never add filler.
- Starting sizes are in `DEFAULT_SIZES` (build_package.py); body 9.5-11 pt is normal.

## QA checklist (after every build)
- Page count as intended; last page well filled.
- Headings uppercase, bold, with a rule; only skill labels bold; bold count within limit.
- Every link (profile links + project links) is clickable in the PDF.
- No forbidden phrases (profile.json) and nothing that isn't in facts.md.
- Look at the PNGs: no overlap, clipping, or single-word last lines.
- Job Description.docx holds a short summary, then the original posting **verbatim**.
