# actuals-snapshot

A Claude Code skill that exports per-person **allocated** hours from Zoho Projects for a month and uploads the CSV to Google Drive. Part 2 of the two-part capacity planning export (see [`project-snapshot`](../project-snapshot/)).

Logged hours are not exported. The planning sheet computes them from the weekly Zoho timesheet xlsx.

---

## Installation

```bash
cp -r claude/skills/actuals-snapshot ~/.claude/skills/
cp -r claude/skills/project-snapshot ~/.claude/skills/   # required: its build script supplies the project list
```

Requires:

- Zoho Projects MCP connector
- Google Drive MCP connector
- Python 3.8+ (stdlib only) for `scripts/process_actuals.py`
- In the repo you run it from:
  - `config.json` with `pm_filter` and `drive.allocations_folder_id`
  - `people.csv` with columns `person_name`, `person_zpuid`, `person_email`, `team`

---

## Usage

```
/actuals-snapshot [month]
```

`month` is optional (`Jun 2026`, `2026-06`, `this month`). It defaults to the current calendar month.

Claude Code will:

1. Build the project list with the same call and filters as `/project-snapshot`
2. Fetch tasks overlapping the month (plus open undated tasks) for each project, 5 projects at a time
3. Record each project's response in `tmp/actuals_partial.ndjson` as it arrives, so an interrupted or compacted run can resume
4. List task owners not yet in `people.csv` and ask you to mark each as `team`, `other` or `skip`
5. Run `process_actuals.py` to share each task's `total_work` among its owners and total the hours per person per project
6. Upload `YYYY_MM_DD_HHMM_allocations.csv` to Drive, delete `tmp/`, and print a summary

---

## Output

| File                               | Location                       | Description                                  |
| ---------------------------------- | ------------------------------ | -------------------------------------------- |
| `YYYY_MM_DD_HHMM_allocations.csv`  | Drive `allocations_folder_id`  | One row per project × person, allocated hrs  |
| `people.csv`                       | Repo root                      | New people appended, missing emails filled in |

If the upload fails or the run stops on an error, `tmp/` is kept so the run can be retried or resumed.
