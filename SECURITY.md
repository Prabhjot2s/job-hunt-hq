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
- `jhq jd <url>` fetches a posting you give it. It refuses private-network and localhost addresses
  (also after redirects) and doesn't fetch LinkedIn, Indeed, ZipRecruiter or Glassdoor.
- Nothing else. There is no telemetry. Claude itself reads files and runs these tools under your Claude
  account, as with anything you do in Claude Code.

## The dashboard
- Binds to 127.0.0.1 only (not reachable from your network).
- Rejects requests whose Host header isn't `127.0.0.1:<port>` or `localhost:<port>` (DNS-rebinding
  protection) and sends no CORS headers, so other websites can't read it.
- Only two write actions, both requiring same-origin, a JSON body under 4 KB and a custom header:
  saving a lead's status (whitelisted values, existing leads only) and opening a folder inside your
  data folder in your file manager.
- Serves files only from inside your data folder (symlinks resolved), PDFs inline and everything else
  as a download.
- Strict Content-Security-Policy, no framing, no external scripts or fonts.

## Reporting a problem
Please open a GitHub issue for bugs. For anything that could expose someone's data, describe it
without including real personal data, or contact the maintainer through the GitHub profile first.
