---
description: Generate a weekly status report for any GitHub Project V2.
---

# Weekly Status Report

## Steps

1. Ask the user for the GitHub project URL:

> What is the GitHub project URL?
> (e.g. `https://github.com/orgs/myorg/projects/1` or `https://github.com/users/me/projects/1`)

2. Fetch the project's actual Status field options:

```bash
python3 "$HOME/.claude/skills/weekly-status-report/scripts/generate_weekly_report.py" \
  --project-url "<URL>" \
  --list-statuses
```

   This prints one status name per line (e.g. `To Do`, `In progress`, `Done on Staging`). These are the only valid values for the status grouping in the next step — never invent or assume status names.

3. Determine the status grouping (which statuses feed the "Closed This Week", "In Progress", and "Next Tasks" sections):

   - If a `CLAUDE.md` file exists in the current working directory, look for an existing status grouping section (a `## Weekly Report Status Grouping` heading with `Closed This Week:` / `In Progress:` / `Next Tasks:` lines).
     - If found, compare every status name it references against the list fetched in step 2.
       - If they match exactly (every grouped name is a real status, and every real status is accounted for in some group) — use this grouping silently, skip asking the user, and go to step 4.
       - If they don't match (a grouped name no longer exists, or a real status isn't covered by any group) — tell the user exactly what's mismatched (e.g. "CLAUDE.md groups 'Ready', but the project's actual statuses are: To Do, In progress, To be tested, On hold, Done on Staging, Done on Live — there is no 'Ready' status"), then ask the three questions below to get a corrected grouping. After the user answers, update the `## Weekly Report Status Grouping` section in `CLAUDE.md` with the corrected grouping.
     - If no such section exists, ask the three questions below, then add a new `## Weekly Report Status Grouping` section to `CLAUDE.md` with the answers (so future runs don't need to ask again). Use this format:
       ```
       ## Weekly Report Status Grouping

       - Closed This Week: <comma-separated statuses>
       - In Progress: <comma-separated statuses>
       - Next Tasks: <comma-separated statuses>
       ```
   - If no `CLAUDE.md` file exists in the current working directory, just ask the three questions below — don't create a `CLAUDE.md` file.

> Here are this project's actual statuses: `<comma-separated list from step 2>`
>
> 1. Which statuses count as **Closed This Week**?
> 2. Which statuses count as **In Progress**?
> 3. Which statuses count as **Next Tasks**? *(for PDF/HTML this feeds "Next 10 Tasks"; for CSV this is all matching open issues)*

4. Ask the user for the output format:

> What output format would you like?
> 1. **PDF** — styled A4 report (requires Chrome)
> 2. **HTML** — same styled report as a standalone HTML file
> 3. **CSV** — one CSV per section saved to a folder (includes all issues, no truncation)

5. **For PDF/HTML only** — check if a project status is available on GitHub:

```bash
python3 "$HOME/.claude/skills/weekly-status-report/scripts/generate_weekly_report.py" \
  --project-url "<URL>" \
  --check-status
```

6. Ask the required questions:
   - **PDF/HTML**: always ask questions 3 and 4 below; only ask questions 1 and 2 if the check returned `STATUS_NOT_FOUND`.
   - **CSV**: skip all questions below — no manual status, questions, or notes apply (the actual GitHub status, if any, is exported automatically into `status.csv`).

> **Before I generate the report:**
>
> 1. *(PDF/HTML only, and only if STATUS_NOT_FOUND)* What is the current project status?
>    *(Choose one: On Track / At Risk / Off Track / Complete / Inactive, or "none")*
> 2. *(PDF/HTML only, and only if STATUS_NOT_FOUND)* Any status description? *(Free text, or "none")*
> 3. *(PDF/HTML only)* Any open questions for the client? *(One per line, or "none")*
> 4. *(PDF/HTML only)* Any notes for the Notes section? *(Free text, or "none")*

7. Determine the output location based on the current working directory:
   - **PDF**: `<cwd>/reports/<slug>-weekly-YYYY-MM-DD.pdf`
   - **HTML**: `<cwd>/reports/<slug>-weekly-YYYY-MM-DD.html`
   - **CSV**: four files in `<cwd>/reports/` — `weekly-YYYY-MM-DD-closed-this-week.csv`, `weekly-YYYY-MM-DD-in-progress.csv`, `weekly-YYYY-MM-DD-next-tasks.csv`, `weekly-YYYY-MM-DD-status.csv`

   Where `<slug>` is the project title slugified (e.g. `prismatch-overview`). For CSV the slug is not needed since filenames are fixed.

8. Tell the user the exact output path(s) and confirm before proceeding:

> Output will be saved to:
> `<resolved path(s)>`
>
> Proceed? (yes/no)

9. Only after confirmation, run the generator:

```bash
python3 "$HOME/.claude/skills/weekly-status-report/scripts/generate_weekly_report.py" \
  --project-url "<URL>" \
  --format <pdf|html|csv> \
  --output-dir "<cwd>/reports" \
  --closed-statuses "<from step 3>" \
  --progress-statuses "<from step 3>" \
  --next-statuses "<from step 3>" \
  [--status "ON_TRACK"]       # PDF/HTML only; include only if STATUS_NOT_FOUND and user provided status; convert display name to uppercase underscore (e.g. "On Track" → "ON_TRACK") \
  [--status-body "…"]        # PDF/HTML only; include only if STATUS_NOT_FOUND and user provided a status description \
  [--questions "…"]          # PDF/HTML only; include only if user provided questions \
  [--notes "…"]              # PDF/HTML only; include only if user provided notes
```

   - `--closed-statuses`/`--progress-statuses`/`--next-statuses` are always required, for every format — pass the comma-separated status names from step 3 verbatim.
   - Omit any other flag whose answer was "none" or blank.
   - For multi-line `--questions`, use `$'line1\nline2'` shell quoting.

10. After the script finishes, tell the user the full path(s) to the generated file(s).

11. If the script fails, show the error and diagnose:
    - Not authenticated: run `gh auth status` and ask user to run `gh auth login`.
    - Chrome PDF failure: an HTML file is saved alongside the expected PDF path — open that as a fallback.

## Report sections

**PDF/HTML:**
1. Overview — project name, description, and current status (with open/closed counts); the status body renders as formatted markdown (headers, bullet lists, bold/italic, code), not raw markdown syntax
2. Open Questions & Client Actions — hidden if empty
3. Closed This Week — issues whose Status is in the "Closed This Week" group, changed within the last 7 days
4. In Progress & To Be Tested — issues whose Status is in the "In Progress" group
5. Next 10 Tasks — issues whose Status is in the "Next Tasks" group, sorted by priority then oldest-first (first 10 shown, overflow link to GitHub)
6. Notes — hidden if none provided

**CSV** (no overview, no questions, no notes):
1. `closed-this-week.csv` — all issues whose Status is in the "Closed This Week" group, changed within the last 7 days
2. `in-progress.csv` — all issues whose Status is in the "In Progress" group
3. `next-tasks.csv` — all issues whose Status is in the "Next Tasks" group, sorted by priority then oldest-first
4. `status.csv` — the actual GitHub project status update, one row: `Status` (e.g. "On Track"), `Summary` (status body, markdown stripped to plain text), `Date` (when it was posted). Header-only if no status update exists on GitHub.

No status name is hardcoded in the report generator — every section is defined entirely by the status grouping from step 3, so this works for any project regardless of its Status field's option names.

## Data sources

GitHub Projects V2 has two distinct, non-overlapping levels of custom fields, and both are fetched:

- **Project-level fields** — set per-item on the project board itself (`ProjectV2Item.fieldValues`), e.g. Status, Size, Assignees.
- **Issue-level fields** — set directly on the issue, independent of any project (`Issue.issueFieldValues`), e.g. Priority, Start date, Target date, Effort. These are a separate GitHub feature from Projects and do **not** appear in `ProjectV2` field queries at all, even though they're visible in the "Fields" section of the issue sidebar in the browser.

Where the same field name exists at both levels, the issue-level value wins (it's the one that's actually populated in practice — the project-level field with the same name is often defined but left empty).

- **CSV**: every field discovered at either level becomes a column — nothing is dropped.
- **HTML/PDF**: the date columns (e.g. "Target", "Start") are driven by the merged Start date/Target date values, which resolve to the issue-level fields whenever they're set.
