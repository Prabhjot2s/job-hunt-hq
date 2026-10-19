# Practical tips (learned the hard way)

## Getting the job description
- Company ATS links (Greenhouse, Lever, Ashby, Workday, SmartRecruiters): `{{JHQ}} jd --text <url>` gives
  the full verbatim text. `{{JHQ}} jd <url>` gives a quick summary of years, pay and work mode.
- JavaScript-only pages: use a browser tool if this Claude app has one (navigate, then read the page
  text), else ask the user to paste the text. Summaries from a web-fetch tool are paraphrased: never
  put them in the "original job description" section.
- Aggregators (LinkedIn, Indeed, ZipRecruiter, Glassdoor) block scripts and often differ from the real
  posting. Search "<company> <title> careers" to find the employer's own page and use that.
- Check the job ID/title in the link matches the role being discussed before building.
- Always confirm location eligibility and the salary currency from the real posting.
- Write the posting text and spec.json with a file-writing tool, not shell heredocs (apostrophes
  break them). Use forward slashes in JSON paths.

## Application forms
- Character limits: count with code before giving an answer; offer two versions when it's tight.
- "Years of experience" boxes: the same figure as the resume summary.
- **Salary expectations:** check whether the posted range is base or total pay, then give a range
  inside it, in the upper middle; never above the posted maximum. If only one number is accepted, use
  the middle of that range. No posted range: give a researched range for the role and city, and say
  it's flexible.
- "Why us" / "anything else": 2-3 short paragraphs (honest motivation, fit in the company's own words,
  1-2 relevant links), plus a short version for tight boxes.
- Skills tag boxes: only skills they really use, the job's most important first, using the site's own
  suggested names.
- Never click submit, upload files or create accounts for them: they do that.

## Outreach (drafts only; the user sends them)
- Plain and specific: who they are, the exact role, one real connection (same school, similar work, a
  detail from the person's profile), one easy ask ("a 15-minute chat this week or next?").
- No flattery, jokes or long "shared journey" openers. Referral asks come after they reply.
- Who to contact: alumni at the company, people on the team, then the recruiter.
- After applying, a referral can still help: "if you're comfortable".

## Side work and gaps
- Don't raise side projects or gaps unprompted in letters. If asked, a short honest answer.

## When files are open
- Excel holding the tracker open blocks writes: ask the user to close it.
- A PDF open in a viewer can block the export: ask them to close it, then rebuild.
