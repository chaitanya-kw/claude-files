---
description: Generate a weekly status report for any GitHub Project V2.
---

# Weekly Status Report

## Steps

1. Ask the user for the GitHub project URL:

> What is the GitHub project URL?
> (e.g. `https://github.com/orgs/myorg/projects/1` or `https://github.com/users/me/projects/1`)

2. Ask the user for the output format:

> What output format would you like?
> 1. **PDF** — styled A4 report (requires Chrome)
> 2. **HTML** — same styled report as a standalone HTML file
> 3. **CSV** — one CSV per section saved to a folder (includes all issues, no truncation)

3. **For PDF/HTML only** — check if a project status is available on GitHub:

```bash
python3 "$HOME/.claude/skills/weekly-status-report/scripts/generate_weekly_report.py" \
  --project-url "<URL>" \
  --check-status
```

4. Ask the required questions:
   - **PDF/HTML**: always ask questions 3 and 4; only ask questions 1 and 2 if the check returned `STATUS_NOT_FOUND`.
   - **CSV**: skip all questions — no status, questions, or notes apply.

> **Before I generate the report:**
>
> 1. *(PDF/HTML only, and only if STATUS_NOT_FOUND)* What is the current project status?
>    *(Choose one: On Track / At Risk / Off Track / Complete / Inactive, or "none")*
> 2. *(PDF/HTML only, and only if STATUS_NOT_FOUND)* Any status description? *(Free text, or "none")*
> 3. *(PDF/HTML only)* Any open questions for the client? *(One per line, or "none")*
> 4. *(PDF/HTML only)* Any notes for the Notes section? *(Free text, or "none")*

5. Determine the output location based on the current working directory:
   - **PDF**: `<cwd>/reports/<slug>-weekly-YYYY-MM-DD.pdf`
   - **HTML**: `<cwd>/reports/<slug>-weekly-YYYY-MM-DD.html`
   - **CSV**: three files in `<cwd>/reports/` — `weekly-YYYY-MM-DD-closed-this-week.csv`, `weekly-YYYY-MM-DD-in-progress.csv`, `weekly-YYYY-MM-DD-next-tasks.csv`

   Where `<slug>` is the project title slugified (e.g. `prismatch-overview`). For CSV the slug is not needed since filenames are fixed.

6. Tell the user the exact output path(s) and confirm before proceeding:

> Output will be saved to:
> `<resolved path(s)>`
>
> Proceed? (yes/no)

7. Only after confirmation, run the generator:

```bash
python3 "$HOME/.claude/skills/weekly-status-report/scripts/generate_weekly_report.py" \
  --project-url "<URL>" \
  --format <pdf|html|csv> \
  --output-dir "<cwd>/reports" \
  [--status "ON_TRACK"]       # PDF/HTML only; include only if STATUS_NOT_FOUND and user provided status; convert display name to uppercase underscore (e.g. "On Track" → "ON_TRACK") \
  [--status-body "…"]        # PDF/HTML only; include only if STATUS_NOT_FOUND and user provided a status description \
  [--questions "…"]          # PDF/HTML only; include only if user provided questions \
  [--notes "…"]              # PDF/HTML only; include only if user provided notes
```

   - Omit any flag whose answer was "none" or blank.
   - For multi-line `--questions`, use `$'line1\nline2'` shell quoting.

8. After the script finishes, tell the user the full path(s) to the generated file(s).

9. If the script fails, show the error and diagnose:
   - Not authenticated: run `gh auth status` and ask user to run `gh auth login`.
   - Chrome PDF failure: an HTML file is saved alongside the expected PDF path — open that as a fallback.

## Report sections

**PDF/HTML:**
1. Overview — project name, description, and current status (with open/closed counts)
2. Open Questions & Client Actions — hidden if empty
3. Closed This Week — issues closed in the last 7 days
4. In Progress & To Be Tested — all active issues
5. Next 10 Tasks — open "Ready" issues sorted by priority then oldest-first (first 10 shown, overflow link to GitHub)
6. Notes — hidden if none provided

**CSV** (no overview, no status, no questions, no notes):
1. `closed-this-week.csv` — all issues closed in the last 7 days
2. `in-progress.csv` — all In Progress and To Be Tested issues
3. `next-tasks.csv` — all open "Ready" issues sorted by priority then oldest-first
