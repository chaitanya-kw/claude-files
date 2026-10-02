# project-snapshot

A Claude Code skill that exports active project metadata from Zoho Projects to a CSV and uploads it to Google Drive. Part 1 of the two-part capacity planning export (see [`actuals-snapshot`](../actuals-snapshot/)).

---

## Installation

```bash
cp -r claude/skills/project-snapshot ~/.claude/skills/
```

Requires:

- Zoho Projects MCP connector
- Google Drive MCP connector
- Python 3.8+ (stdlib only) for `scripts/build_projects.py`
- A `config.json` in the repo you run it from:

```json
{
  "pm_filter": ["<PM name>", "<PM name>"],
  "drive": { "projects_folder_id": "<Drive folder ID>" }
}
```

The Zoho portal ID is hardcoded in `SKILL.md` (Constants). Change it if you use a different portal.

---

## Usage

```
/project-snapshot [month]
```

`month` is optional (`Jun 2026`, `2026-06`, `this month`, `next month`). It defaults to the current calendar month.

Claude Code will:

1. Read `pm_filter` and the Drive folder from `config.json`
2. Fetch the project list with one `get_projects_list` call (paginated at 100). The response is saved to a file and never read into context
3. Run `build_projects.py`, which keeps active projects (`In Progress`, `UAT`, `Warranty`, `On Hold`) matching the PM filter on owner, project manager, Manager 2.0 or Assigned To, and computes a pro-rated `monthly_budget`
4. Upload `YYYY_MM_DD_HHMM_projects.csv` to Drive and delete the local copy
5. Print a summary with the Drive link

---

## Output

| File                             | Location                             | Description                        |
| -------------------------------- | ------------------------------------ | ---------------------------------- |
| `YYYY_MM_DD_HHMM_projects.csv`   | Drive `projects_folder_id`           | One row per active project         |

If the upload fails, the CSV stays in `tmp/` as the only copy.

`monthly_budget = estimated_hours × (days of the project inside the month ÷ project duration in days)`. It is left empty when dates or estimated hours are missing.
