# snm-tnm-monthly-report-generator

Generates a branded Kilowott monthly client report as a self-contained HTML file, combining S&M (Support & Maintenance) and T&M (Time & Materials) sections.

## What it does

- Accepts task lists in any format (CSV, Google Doc, screenshot of a PM tool, `.md` file, or typed in chat), mixed across multiple messages
- Splits S&M work into **Support** (6 categories) and **Maintenance** (5 categories) with independent category inference rules
- Tracks task status (`Open` / `In Progress` / `Resolved` / `Deployed`) and only shows a deployment date once a task is `Deployed`
- Drafts narrative Summary / Blockers / Value Add sections grounded in the task data, always in client-facing tone (never "the client" or "they")
- Computes Support Overview and Maintenance Overview aggregate tables, omitting zero-task categories
- Renders standalone "Findings" sections for each Maintenance scan category present (Security / Uptime / Accessibility)
- Optionally includes Core Framework Updates and Plugin & Package Updates sections when version/package data is available
- Presents the full draft in chat for confirmation before generating the HTML file
- Produces a print-ready, self-contained HTML file matching the Kilowott report template

## Trigger phrases

Only triggers when the request explicitly references an S&M or T&M project:

- "generate the S&M report"
- "create the T&M report for June"
- "build the S&M/T&M report for [month]"
- "turn this S&M task list into a report"

Does **not** trigger for general monthly summaries, plain-text reports, internal status updates, or reports for projects that are not explicitly S&M or T&M.

## Workflow

1. **Confirm project, client name, and month** — read the project name from Claude Project context if available, confirm the client name from conversation/memory, and default the reporting period to the current month unless told otherwise.
2. **Gather task data** and fill in required fields (see below), inferring `type` and `category` where possible and asking when ambiguous.
3. **Draft narrative sections** (Summary, Blockers, Value Add) from the task data.
4. **Present the full draft in chat** (not an artifact) for confirmation, and re-confirm after any corrections.
5. **Compute aggregates** — Support Overview, Maintenance Overview, S&M Updates table, T&M Updates table, Scan Findings.
6. **Core Framework / Plugin & Package Updates** — included only if version/package data is found or supplied; each can be skipped independently.
7. **Generate the HTML file** from `references/report-template.md`.
8. **Save and present** the file.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Project name | Yes | Confirmed in Step 1; appears in the report title |
| Client name | Yes | Confirmed in Step 1; used in narrative text instead of "the client" |
| Month + year | Yes | Defaults to the current month unless overridden |
| S&M task list | Yes | See formats below |
| T&M task list | No | Omit the T&M section entirely if empty |

### Accepted task list formats

CSV (header row required, columns in any order), a Google Doc link, a screenshot of a PM tool (parsed visually), a `.md` file, or freeform/table text typed directly in chat.

**Required fields per task:**

| Field | Notes |
|---|---|
| `description` | free text |
| `section` | `SM` or `TM` — defaults to `SM` if unstated |
| `type` | *(SM tasks only)* `Support` or `Maintenance` — inferred from description if not given |
| `category` | depends on `type`; see `references/category-inference.md` |
| `status` | `Open` / `In Progress` / `Resolved` / `Deployed` — defaults to `Deployed` |
| `priority` | High / Medium / Low |
| `effort_hr` | numeric, hours |
| `date` | any unambiguous format |

**Maintenance-only, per category (not per task):** `Frequency` and `Next Schedule` — asked once per maintenance category that has at least one task this month. `Note` is optional and left blank if not provided.

## Output

A file named `YYYY_MM_DD_HHMM-monthly-report-<project-slug>.html`, timestamped in IST (UTC+5:30), saved to `/mnt/user-data/outputs/` and presented via `present_files`.

Report sections (numbered sequentially, gaps closed if any are omitted): Summary, Blockers, Value Add, Support Overview, Maintenance Overview, Support & Maintenance Updates, Core Framework Updates (optional), Plugin & Package Updates (optional), one standalone section per qualifying scan category, Time & Machinery Updates (omitted if no T&M tasks), Footer.

## Install

```bash
mkdir -p ~/.claude/skills/snm-tnm-monthly-report-generator
# Unzip the .skill archive and copy SKILL.md
unzip snm-tnm-monthly-report-generator.skill -d /tmp/skill_extracted/
cp /tmp/skill_extracted/snm-tnm-monthly-report-generator/SKILL.md ~/.claude/skills/snm-tnm-monthly-report-generator/
cp -r /tmp/skill_extracted/snm-tnm-monthly-report-generator/references ~/.claude/skills/snm-tnm-monthly-report-generator/
```

## References

- `references/report-template.md` — annotated HTML template with all inline styling
- `references/category-inference.md` — keyword rules for inferring `type` and the Support/Maintenance category
