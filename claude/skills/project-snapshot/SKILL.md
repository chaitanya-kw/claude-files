---
description: Export active project metadata from Zoho Projects. Builds YYYY_MM_DD_HHMM_projects.csv in tmp/, uploads it to Google Drive and deletes the local copy.
---

# Zoho Project Snapshot Export

Export active project metadata from Zoho Projects, build `YYYY_MM_DD_HHMM_projects.csv` in `tmp/`, and upload it to the Drive projects folder. Nothing is kept locally: Drive holds the exports.

One API call does the work: `get_projects_list` already returns every field the CSV needs, so there are **no per-project detail calls**. The list response is processed by a script and never needs to pass through the conversation.

---

## Invocation

```
/project-snapshot [month]
```

`month` is optional. Examples of accepted values: `Jun 2026`, `June 2026`, `2026-06`, `this month`, `next month`.

If no argument is supplied, default to the **current calendar month** using the system date — do not ask the user.

---

## Constants

- Portal ID: `60037513197`
- MCP tool prefix: `mcp__claude_ai_Zoho_Projects__`
- Active statuses: `In Progress`, `UAT`, `Warranty`, `On Hold`
- Exclude always: status `Complete` / `Completed` or `is_completed = true` (even when the PM filter matches), plus `In Backlog`, `Presales` and any other status not listed above
- Presales projects (`engagement_model` = `PreSales` or `stage` = `Sales`) are included when they match the PM filter
- PM filter: `owner`, `project_manager`, `manager_2_0` (Manager 2.0) or `assigned_to` (Assigned To) contains any name in `config.json` → `pm_filter` (case-insensitive). Manager 2.0 and Assigned To are user objects; their `full_name`, `name` and `email` are matched
- Config: `config.json` in the repo root — `pm_filter` (list of names), `drive.projects_folder_id` (upload target)
- Build script: `scripts/build_projects.py` in this skill directory

---

## Step 0 — Read config

Read `config.json` from the repo root. Take `pm_filter` (a non-empty list of names) and `drive.projects_folder_id`.

- File missing or `pm_filter` empty → print an error and stop. Do not guess names.
- `drive.projects_folder_id` missing → continue, but skip the upload in Step 4 and say so in the summary.

Print: `PM filter: <names joined with ", ">`

---

## Step 1 — Resolve target month

Derive `target_month` (`YYYY-MM`) from the argument or system date.

Print: `Target month: <target_month>`

---

## Step 2 — Fetch the project list

Call `mcp__claude_ai_Zoho_Projects__get_projects_list`:

- `path_variables`: `{"portal_id": "60037513197"}`
- `query_params`: `{"per_page": 100}`

The response is large (~800 KB for ~90 projects), so Claude Code saves it to a file and returns the path. **Do not read the file or copy its contents** — pass the path to the script in Step 3.

- **Saved to a file:** note the path.
- **Returned inline** (only if the portal ever becomes small): write the response text exactly as returned to `tmp/projects_list_p1.json`, and use that path.
- **Pagination:** if a page holds exactly 100 projects, fetch `page: 2`, `3`, … with the same `per_page` until a page holds fewer than 100. Keep every page's path. (The response has no `page_info`; to count projects in a saved file without reading it into the conversation, run `python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(len(d['data']['result']))" <path>`.)

If the call fails, print the error and stop.

---

## Step 3 — Build the CSV

Run from the repo root, passing every page's path:

```bash
python3 <skill_dir>/scripts/build_projects.py --month <target_month> <page1_path> [<page2_path> ...]
```

The script:

- reads `pm_filter` from `config.json`;
- filters to `project_type = active`, the active statuses, and the PM filter (owner, project manager, Manager 2.0 or Assigned To). Presales projects that match are kept;
- computes `monthly_budget` (below);
- writes `tmp/YYYY_MM_DD_HHMM_projects.csv` (IST timestamp);
- prints a summary. **The last printed line is the CSV path.**

If it exits with an error (no projects in the response, none passing the filter, missing config), print the error and stop.

### monthly_budget

```
if start_date missing OR end_date missing OR estimated_hours is null:
    monthly_budget = ""
else:
    overlap_start = max(start_date, month_start)
    overlap_end   = min(end_date, month_end)
    overlap_days  = max(0, (overlap_end - overlap_start).days + 1)
    duration_days = max(1, (end_date - start_date).days + 1)
    monthly_budget = round(estimated_hours * overlap_days / duration_days, 2)
```

### CSV columns (as written by the script)

| Column              | Source                    |
| ------------------- | ------------------------- |
| `project_id`        | `id`                      |
| `project_name`      | `name`                    |
| `project_key`       | `key`                     |
| `status`            | `project_status`          |
| `status_label`      | `status.name`             |
| `stage`             | `stage`                   |
| `engagement_model`  | `engagement_model`        |
| `skills_required`   | `skill[]` joined with `;` |
| `client_name`       | `client_name`             |
| `account_manager`   | joined with `;`           |
| `invoicing_type`    | `invoicing_type`          |
| `priced_by_finance` | `priced_by_finance`       |
| `start_date`        | `start_date`              |
| `end_date`          | `end_date`                |
| `estimated_hours`   | `estimated_hours`         |
| `ballpark_hours`    | `ballpark_hours_2_0`      |
| `monthly_budget`    | computed above            |
| `percent_complete`  | `percent_complete`        |
| `csat`              | joined with `;`           |
| `assigned_to`       | `assigned_to.full_name`   |
| `project_folder`    | `project_folder`          |
| `url_live`          | `url_live` (bare `https://` → empty) |
| `url_staging`       | `url_staging` (bare `https://` → empty) |
| `git_hub`           | `git_hub`                 |
| `project_manager`   | `project_manager`         |
| `description`       | `description`, HTML stripped to plain text |
| `risk_category`     | joined with `;`           |
| `seo`               | `seo`                     |
| `sold_hours`        | `sold_hours_2_0`          |
| `contract`          | `contract`                |
| `delivery_tier`     | `delivery_tier`           |
| `roas`              | `roas`                    |
| `quality`           | `quality`                 |
| `design_adherence`  | `design_adherence`        |
| `sm_engagement`     | `sm_engagement`           |
| `uat_report`        | `uat_report`              |
| `re_allocation_note`| `re_allocation_note`      |
| `internal_delivery_date` | `internal_delivery_date` |
| `uat_date`          | `uat_date`                |
| `designers`         | joined with `;` (`full_name`) |
| `completed_time`    | `completed_time`          |
| `hsid`              | `hsid`                    |

Fields Zoho leaves empty are omitted from the response; the script writes them as empty strings.

---

## Step 4 — Upload to Drive

Read the CSV written in Step 3 and call `mcp__claude_ai_Google_Drive__create_file`:

- `title`: the CSV filename (e.g. `2026_10_02_1538_projects.csv`)
- `parentId`: `drive.projects_folder_id`
- `textContent`: the CSV file contents, exactly as written
- `contentMimeType`: `text/csv`
- `disableConversionToGoogleType`: `true`

If the upload succeeds, delete this run's local files: the CSV and any `tmp/projects_list_p*.json` from Step 2. Delete only these files, not the whole `tmp/` folder, which may hold an `/actuals-snapshot` partial run. Remove `tmp/` itself if it is then empty:

```bash
rm -f tmp/<csv filename> tmp/projects_list_p*.json && rmdir tmp 2>/dev/null || true
```

If the upload fails, report it and **keep** the CSV in `tmp/`: it is the only copy. Ask the user whether to retry.

---

## Step 5 — Print summary

```
Run complete — <target_month>
PM filter:               <names>
Projects in list:        <N>
Projects exported:       <N>
Missing budget (has hrs):<N> — <names if any>
Null estimated_hours:    <N> — <names if any>
Drive:  <viewUrl of the uploaded file, or "upload failed" / "skipped — no folder in config.json">
```

---

## Error handling

- Project list call fails → print error, stop.
- Script exits with an error → print it, stop. Do not build the CSV by hand.
- `tmp/` folder does not exist → created by the script.

---

## Data integrity rules

- Every value must come from the `get_projects_list` response(s) fetched in this run.
- Never reuse data from memory, conversation history, or prior runs.
- Never hardcode or approximate any field value.
