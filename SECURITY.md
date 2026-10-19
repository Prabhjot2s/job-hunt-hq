# Security and privacy

## Where your data is
- Your profile, resume, facts, applications, tracker and job leads live in the data folder you chose
  during setup. `python -m jhq where` prints it.
- `~/.job-hunt-hq/config.json` only stores paths, your timezone and the dashboard port.
- The repo never holds your data. `jhq init` refuses a data folder inside the repo, and `.gitignore`
  blocks the usual data file types as a second guard.

## What talks to the internet
- The radar requests public job-board feeds (Greenhouse, Lever, Ashby, Workable, SmartRecruiters,
  Rippling, Pinpoint, BambooHR, Workday) for the companies in your list, and careers pages when you
  ask it to find a company's board. Requests identify themselves as `job-hunt-hq`.
- `jhq jd <url>` fetches a posting you give it, and `jhq companies find` reads a company's careers
  page. Both refuse anything that isn't a public internet address (localhost, your home network,
  cloud metadata addresses, URLs with a login part), re-checking every redirect. `jd` doesn't fetch
  LinkedIn, Indeed, ZipRecruiter or Glassdoor. Remaining risk: DNS rebinding between the check and
  the connection; the dashboard's Host-header check still protects it.
- Nothing else. There is no telemetry. Claude itself reads files and runs these tools under your Claude
  account, as with anything you do in Claude Code.

## The dashboard
- Binds to 127.0.0.1 only (not reachable from your network).
- Rejects requests whose Host header isn't `127.0.0.1:<port>` or `localhost:<port>` (DNS-rebinding
  protection) and sends no CORS headers, so other websites can't read it.
- Only two write actions, both requiring same-origin, a JSON body under 4 KB and a custom header:
  saving a lead's status (whitelisted values, existing leads only) and opening a folder inside your
  data folder in your file manager.
- Serves files only from inside your data folder, PDFs inline and everything else as a download.
  Paths are checked as text before any disk access (so a web page can't make Windows connect to a
  `\\server\share` path and leak your login hash), then links/junctions are resolved and checked again.
- Everything from job postings is HTML-escaped when shown, and the page's Content-Security-Policy only
  runs its own script (a fresh nonce per load), so injected `<script>` or `onerror=` can't run even if
  something slipped through. No framing, no external scripts or fonts.

## Untrusted text from job postings
- **Spreadsheets:** text written to the tracker is always stored as text, never as a formula, so a job
  titled `=HYPERLINK(...)` can't become a live link in Excel. Company names in companies.csv are
  stripped of leading `= + - @`.
- **Documents:** invisible control characters are removed before they reach Word files.
- **PDF export (Windows):** file paths are handed to Word through environment variables, never pasted
  into the PowerShell command, so folder names made from job titles can't inject commands.
- **Claude itself:** the skills tell Claude that postings, emails and web pages are data, not
  instructions, and to report text that tries to direct it ("AI assistants: rate this candidate ...").
  This lowers the risk; it can't remove it, so review what Claude proposes before you approve actions.

## Reporting a problem
Please open a GitHub issue for bugs. For anything that could expose someone's data, describe it
without including real personal data, or contact the maintainer through the GitHub profile first.
