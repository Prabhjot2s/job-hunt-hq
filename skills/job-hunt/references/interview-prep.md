# Interview prep

Adapted from MadsLorentzen/ai-job-search (MIT): /interview and interview-prep guidance.

## When
- On request: "prep me for <company>", "I have an interview with X", "mock interview".
- From the radar's email check: an interview invite for a tracked application (the radar builds the
  pack without asking questions; unknown stage = Recruiter Screen).
- Don't rebuild a pack that exists for the same stage; make a new file for the next stage.

## Step 1: Load the application
1. `{{JHQ}} tracker search "<company>"`: status, dates, Main Strengths, Main Gaps, Notes.
2. The job folder: Job Description.docx (the posting applied to), the submitted resume PDF (what the
   interviewer read), the cover letter if sent, tracker_meta.json, earlier `Interview Prep - *.docx`
   (the best input for the next stage).
3. facts.md (truth), star-stories.md, rules.md.
4. Stage, date, format and interviewer names from the invite, else ask (scheduled runs: write
   "unknown" and continue).

## Step 2: Research (verified only)
- The company's own site (search its name; don't follow links from the posting), news from the last
  6 months, what the team/product does, stated priorities. 2-3 verified "conversation hooks", each with
  its source URL.
- Interviewers, if named: public professional info from a web search only, to guess their angle
  (recruiter = timeline, pay, motivation; hiring manager = fit and how you work; peer = technical depth).
- Anything unverified stays out.

## Step 3: Build the pack
Write markdown, then `{{JHQ}} md2docx prep.md "<job folder>/Interview Prep - <Stage>.docx"`.
Stages: Recruiter Screen, Hiring Manager, Technical, Case, Panel, Final.

Sections:
1. **Header:** company, role, stage, date/time + timezone, format, interviewers, posting link.
2. **30-second pitch:** "Tell me about yourself", matching the submitted resume's summary.
3. **Likely questions (8-12):** from earlier-stage notes, each Main Gap (with an honest bridge:
   acknowledge, nearest real experience, how they'd ramp), the posting's must-haves, and the stage type.
4. **STAR mapping:** which story from star-stories.md answers each behavioural question, plus the one
   line to adapt. No story fits? Draft one from facts.md only, mark it `NEW - check`, offer to add it.
5. **Technical warm-up** (technical stages): 3-5 practice questions on their stack at the right level,
   with short model answers.
6. **Consistency brief:** the resume/letter claims most likely to be probed, each with the true detail
   behind it. Nothing in the room that isn't on paper; everything on paper defended in depth.
7. **Tough questions:** why leaving / why now, gaps, salary (see tips.md), "why us" (from the hooks).
8. **Questions to ask them (4-6)** for this stage, minus anything the research already answered.
9. **Logistics:** time-zone check, format tips, a thank-you note draft for within 24 hours (the user
   sends it themselves).
About 3-5 pages, plain language, the user's voice.

## Step 4: Record
Tracker: only new facts (an event, `Notes+` "Interview prep pack built"). New true facts that came up:
add to facts.md / star-stories.md only with the user's OK.

## Mock interview (only when asked)
In chat: warm-up, 2-3 role-specific technical questions, 1-2 behavioural questions tied to the
posting, one curveball. After each answer: what worked, what to sharpen, which story would land
better. Coach toward their natural style, not a script.

## After the interview
Update the row (event, `Notes+` with what was asked and any concerns) so the next stage's pack starts
from it.
