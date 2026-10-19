# Installing Job Hunt HQ (instructions for Claude)

Claude: the user asked you to install this. Follow these steps, explain briefly what each does, and stop
to ask if anything fails. Don't change files outside the repo folder and `~/.claude/skills/` except the
user's chosen data folder later.

1. **Where:** if the repo isn't cloned yet, ask where to put it (suggest the home folder) and run
   `git clone https://github.com/Prabhjot2s/job-hunt-hq.git <folder>`. No git? Download the ZIP from the
   GitHub page and unzip it.
2. **Python:** check `python --version` (or `python3 --version`): 3.9 or newer is needed. If missing, tell
   the user how to install it for their system (python.org, or `brew install python` on a Mac) and wait.
3. **Install:** from the repo folder run `python install.py` (`python3` on macOS/Linux). It creates
   `.venv/`, installs the packages, copies the skills `job-hunt`, `job-hunt-setup` and `job-radar` into
   `~/.claude/skills/`, and runs a health check. If a skill folder with the same name already existed
   and wasn't from this project, the installer moved it aside and says where.
4. **PDF export:** the health check lists "PDF export". If it shows nothing, the user needs Microsoft
   Word or the free LibreOffice (https://www.libreoffice.org/download/). Documents still build as .docx
   without it.
5. **Skills load:** new skills are picked up in a new conversation. Tell the user to start a new
   Claude Code chat (or restart the app) and say **"set up Job Hunt HQ"**. If you can already see the
   job-hunt-setup skill, start it now.

**Updating later:** `git pull` in the repo folder, then `python install.py` again (their data folder is
never touched).

**Uninstalling:** `python install.py --remove` removes the skills; then delete the repo folder. Their
data folder and `~/.job-hunt-hq/` stay until they delete them.
