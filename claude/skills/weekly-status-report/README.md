# weekly-status-report

A skill that generates a weekly status report for any GitHub Project V2 in PDF, HTML, or CSV format. Runs in Claude Code and on claude.ai.

---

## Installation

**Claude Code**

```bash
cp -r claude/skills/weekly-status-report ~/.claude/skills/
```

**claude.ai**: zip the folder (`cd claude/skills && zip -r weekly-status-report.zip weekly-status-report`) and upload it under Settings → Capabilities → Skills.

Requires:
- Python 3.8+
- GitHub access: the `gh` CLI, logged in (`gh auth login`). Where `gh` isn't installed (claude.ai), a `GH_TOKEN` or `GITHUB_TOKEN` with `repo` and `read:project` scopes.
- For PDF output, Chrome/Chromium on `$PATH` or Playwright's Chromium. Without either, the HTML is saved instead.

The skill bundles `scripts/generate_weekly_report.py`, so there's nothing else to install.

---

## Usage

Trigger from any session:

```
generate a weekly status report
create a project status report
run the weekly report for my GitHub project
```

Claude asks for the GitHub project URL, then for the status grouping (which of the project's real Status options count as Closed This Week, In Progress and Next Tasks) and the output format. Then it generates the report. In Claude Code the grouping is saved to the working directory's `CLAUDE.md` and reused on later runs.

### Output formats

| Format | Description |
| ------ | ----------- |
| **PDF** | Styled A4 report |
| **HTML** | The same styled report as a standalone file |
| **CSV** | Four CSV files, no truncation: one per section plus the project status |

### Report sections (PDF/HTML)

1. Overview: project name, description, current status, open/closed counts
2. Open Questions & Client Actions: hidden if empty
3. Closed This Week: issues in the "Closed This Week" statuses, changed in the last 7 days
4. In Progress & To Be Tested: issues in the "In Progress" statuses
5. Next 10 Tasks: issues in the "Next Tasks" statuses, sorted by priority then age
6. Notes: hidden if none provided

No status name is hardcoded; every section comes from the grouping you choose.

### Output location

- **Claude Code**: `<cwd>/reports/`
- **claude.ai**: `/mnt/user-data/outputs/`, shared with you through the file panel

File names:
- PDF/HTML: `<slug>-weekly-YYYY-MM-DD.pdf` / `.html`
- CSV: `weekly-YYYY-MM-DD-closed-this-week.csv`, `-in-progress.csv`, `-next-tasks.csv`, `-status.csv`

Claude confirms the output path before running.

### Troubleshooting

- **Not authenticated**: run `gh auth login`, or set `GH_TOKEN`
- **PDF fails**: an HTML fallback is saved next to the expected PDF path. Open that instead
