# monthly-value-report (monthly report v2)

The second version of the monthly client report, next to `snm-tnm-monthly-report-generator` (v1). v1 builds an S&M/T&M
report from task lists you supply. v2 builds the report from the data itself: Zoho billable hours, GitHub issue time
logs, closed issues and merged PRs. It focuses on **the value the dev team delivered in the month**, with hours shown
at priority level.

Output is a PDF and/or Gmail-paste HTML in the Kilowott house style used by the weekly reports.

## What it does

- Reads the month's billable Zoho time logs (timesheet xlsx export) of **everyone** on the client's projects: devs,
  project managers, senior staff. Anyone not in the config is flagged and the skill asks what they do
- Shows support & maintenance (S&M) projects in their own task table, apart from development, and puts role-based
  time (e.g. planning and management) on its own line
- Pulls dev time-log comments from the configured GitHub repos and places each billable hour under a priority (parent
  issue), filling gaps from Zoho notes. Leftover hours are spread over the dev's own month mix. GitHub logs on unbilled
  days are ignored
- Lists what shipped: issues closed as completed and PRs merged into each repo's deploy branch, rolled up to priorities
- Lets you take a week's hours from an already-sent weekly report when the Zoho export is incomplete
- Flags weekdays with no billable time (holidays from the config are skipped) and issues not under a priority
- Shows the full draft in chat for approval before writing any file

## Report layout

1. **The month at a glance**: intro, plus hour cards per dev, tasks completed and changes shipped
2. **Highlights**: the 3–5 most valuable outcomes
3. **What we delivered**: per priority, the hours, a one-line *Value* statement and the delivered outcomes
4. **Where the time went**: priority × dev hours table with each priority's share

It covers only the month in question: no plans or next steps.

## Trigger phrases

- "monthly report", "monthly value report", "October report for <client>"
- "/monthly-value-report"

## Requirements

- `gh` CLI, logged in with read access to the repos (write access only to link parents, after approval)
- Python 3 with `openpyxl` (the skill sets up a `.venv` in the project if none exists)
- `google-chrome` (headless PDF printing) and `pdfinfo` / `pdftoppm` (poppler-utils)
- The month's Zoho timesheet xlsx (finance export), normally from a Google Drive folder, downloaded to `~/Downloads`

## Install

```bash
cp -r claude/skills/monthly-value-report ~/.claude/skills/
```

Then, in each project folder, the first run creates `report.config.json` from `config.example.json` with you:
GitHub owner, repos, project number and deploy branches; devs (short name, Zoho user name, GitHub login); Zoho
project IDs; the priorities source (a markdown file of `[repo #n]` links, or a parent label); holidays; and optional
`epic_overrides` and `labels`.

## Verify

```bash
ls ~/.claude/skills/monthly-value-report/SKILL.md
cd <project folder> && python3 ~/.claude/skills/monthly-value-report/scripts/monthly_report.py 2026-10 <work dir> --preview
```

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | Skill body: the steps, approval gate and rules |
| `config.example.json` | Template for the per-project `report.config.json` |
| `scripts/cfg.py` | Config loading, priority list, sub-issue roll-up |
| `scripts/zoho_hours.py` | Month's billable Zoho rows → `zoho.csv` |
| `scripts/gh_hours.py` | GitHub time-log comments → `github_hours.csv` |
| `scripts/delivered.py` | Closed issues and merged PRs → `delivered_issues.csv`, `merged_prs.csv` |
| `scripts/monthly_report.py` | Gap list (`--gaps`), draft (`--preview`), PDF/HTML build |
| `scripts/kw_report.py` | Kilowott house-style HTML helpers and headless-Chrome PDF printing |
