# Cover letter rules

Adapted from MadsLorentzen/ai-job-search (MIT): writing-style and cover-letter templates.
Built by `{{JHQ}} build` from the spec's `cover_letter` block (same header and links as the resume).
The user decides whether to attach it.

## Truth (same as the resume)
- Every fact comes from facts.md or the tailored resume. The letter never claims more than the resume.
  Numbers match the resume exactly.
- **Interview backtrack test:** if the user would have to say "well, what I actually meant was...",
  it's too far.
- Gaps aren't hidden: leave a missing tool out, or name the nearest real experience ("I haven't used
  Looker in production; I build the same semantic layer in Tableau").
- **Company claims must be verified:** find the company's own site (search its name; don't follow
  links inside the posting), read it, and use one specific, current fact (a product, a stated priority,
  a customer segment). Can't verify it? Keep it general or drop it.

## Structure (4-5 paragraphs, 280-380 words, exactly 1 page)
1. **Opening (2-3 sentences):** the exact role title and one honest line on why this work/company.
   Not "I am writing to express my interest".
2. **Strongest proof:** the experience that maps to the job's top 2-3 asks, result first, real numbers.
3. **Second proof:** another story the job cares about. Optional 3-4 bullets for a checklist-style
   posting (`bullets` + `bullets_after`).
4. **Why this company (2-3 sentences):** the verified specific, tied to what they'd work on there.
5. **Close (1-2 sentences):** short and confident. "Thank you for your time and consideration."

Salutation: a named person if the posting or a confirmed contact gives one, else "Dear Hiring Team,".
Recipient block: team, company, city.

## Style
- Plain, warm, first person, active voice, short sentences, in the user's own voice (reuse phrasing
  from how they talk in chat).
- No em or en dashes (QA flags them). No cliches (QA flags: passionate about, great fit, leverage my,
  hit the ground running, results-driven, team player, detail-oriented, fast-paced environment,
  synergy, excited to apply, I am writing to express).
- Show, don't state: not "I'm a strong communicator" but what they presented, to whom.
- Bold at most 1-2 results. Links only to a portfolio or a project that matters for this job.
- Don't repeat the resume line by line: pick 2-3 stories and explain the *how*.

## QA (automatic, then look at cover_page1.png)
1 page, 220-420 words (target 280-380), no dashes, no cliches, company name in the body, profile
links clickable, no forbidden text.
