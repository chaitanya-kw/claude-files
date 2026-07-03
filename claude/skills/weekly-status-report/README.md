# weekly-status-report

A Claude Code skill that generates a weekly status report for any GitHub Project V2 in PDF, HTML, or CSV format.

---

## Installation

```bash
cp -r claude/skills/weekly-status-report ~/.claude/skills/
```

Requires:
- Python 3.8+
- `gh` CLI authenticated (`gh auth login`)
- Chrome/Chromium on `$PATH` for PDF output (HTML output works without it)

The skill bundles `scripts/generate_weekly_report.py` — no separate install needed.

---

## Usage

Trigger from any Claude Code session:

```
generate a weekly status report
create a project status report
run the weekly report for my GitHub project
```

Claude Code will ask for the GitHub project URL and output format, then generate the report.

### Output formats

| Format | Description |
| ------ | ----------- |
| **PDF** | Styled A4 report — requires Chrome |
| **HTML** | Same styled report as a standalone file |
| **CSV** | Three CSV files with no truncation — one per section |

### Report sections (PDF/HTML)

1. Overview — project name, description, current status, open/closed counts
2. Open Questions & Client Actions — hidden if empty
3. Closed This Week — issues closed in the last 7 days
4. In Progress & To Be Tested — all active issues
5. Next 10 Tasks — open "Ready" issues sorted by priority then age
6. Notes — hidden if none provided

### Output location

Reports are saved to `<cwd>/reports/`:

- PDF/HTML: `<slug>-weekly-YYYY-MM-DD.pdf` / `.html`
- CSV: `weekly-YYYY-MM-DD-closed-this-week.csv`, `weekly-YYYY-MM-DD-in-progress.csv`, `weekly-YYYY-MM-DD-next-tasks.csv`

Claude Code confirms the output path before running.

### Troubleshooting

- **Not authenticated**: run `gh auth login`
- **PDF fails**: an HTML fallback is saved alongside the expected PDF path — open that instead
