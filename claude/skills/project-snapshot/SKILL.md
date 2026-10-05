---
description: Export active project metadata from Zoho Projects. On first run in a folder, sets up config.json, people.csv and the Google Drive folders. Builds YYYY_MM_DD_HHMM_projects.csv in tmp/, uploads it to Google Drive and deletes the local copy.
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
- Unassigned owner zpuids (used by `/actuals-snapshot`): `0`, `282451000000055461` — the portal's placeholder for "no owner". The portal is shared by every PM, so these never change
- Config: `config.json` in the workspace (current directory) — `pm_filter` (list of names), `drive.projects_folder_id` (upload target). Created by Step 0 if missing
- Scripts (in `<skill_dir>/scripts/`): `build_projects.py` builds the CSV; `workspace.py` does preflight, setup and cleanup
- Counterpart skill: `actuals-snapshot`, installed as a sibling folder (`<skill_dir>/../actuals-snapshot`)

---

## Step 0 — Preflight and setup

Run this on every invocation. `<skill_dir>` is this skill's base directory, shown when the skill loads. Write every path with forward slashes — they work on Windows too. The **workspace** is the current directory: `config.json`, `people.csv` and `tmp/` live there. It does not need to be a git repo or contain a `CLAUDE.md`.

### 0a — Find Python

Run `python3 --version`. If that fails or prints nothing, try `python --version`, then `py -3 --version`. Use the first that reports Python 3.8 or later as `<py>` for every command in this run. If none works, stop and tell the user to install Python 3 and make it available on PATH.

### 0b — Check the install and workspace

```bash
<py> <skill_dir>/scripts/workspace.py check
```

It prints JSON:

- `skills.actuals-snapshot.installed` is `false` → **warn** (do not stop): `actuals-snapshot is not installed next to this skill (expected at <path>). /project-snapshot works on its own, but /actuals-snapshot needs both skills installed side by side in the same skills folder.`
- `skills.project-snapshot.missing_scripts` is non-empty → stop: this skill's install is incomplete; reinstall it.
- `ready` is `true` → go to Step 0d.
- Otherwise → Step 0c.

### 0c — Setup (first run in this workspace, or incomplete config)

Ask only for what `config.missing` lists. Keep values already in `config.json`.

1. **Confirm the folder.** `Set up the Zoho snapshot workspace in <workspace>? config.json and people.csv will be created here. (yes / no)` On `no`, stop and tell the user to start Claude Code in the folder they want to use.
2. **PM names** (if `pm_filter` is missing): `Which name(s) should the PM filter match? Use your name as it appears in Zoho (owner, project manager, Manager 2.0 or Assigned To). Separate several names with commas.`
3. **Drive folders** (if either folder ID is missing): `Create new Google Drive folders for the exports, or use folders you already have? (create / existing)`
   - **create** — call `mcp__claude_ai_Google_Drive__create_file` four times with `contentMimeType` `application/vnd.google-apps.folder` and no content (if that is rejected, use `mimeType` with the same value instead):
     1. `title` `Zoho exports - <first PM name>`, no `parentId` (My Drive). Its `id` is the root folder.
     2. `title` `projects`, `parentId` = root id.
     3. `title` `allocations`, `parentId` = root id.
     4. `title` `timesheets`, `parentId` = root id.
   - **existing** — ask for the projects, allocations and timesheets folder links (timesheets is optional for the skills, but the planning sheet needs it). Check each with `mcp__claude_ai_Google_Drive__get_file_metadata` (the ID is the part after `folders/`). It must exist and have mime type `application/vnd.google-apps.folder`; otherwise ask again.
4. **Write the workspace** (links or bare IDs both work; pass only the options you have):

```bash
<py> <skill_dir>/scripts/workspace.py init --pm "<name>" [--pm "<name>" ...] --projects-folder <link> --allocations-folder <link> --timesheets-folder <link> [--root-folder <link>]
```

   It merges into an existing `config.json`, creates `people.csv` with only its header row if missing, and prints a `SETTINGS BLOCK`. If only `people.csv` is missing, run `init` with no options.

5. **Hand over the sheet settings.** Whenever folders were created or entered in this step, show the user this, filling in the three lines **exactly** as the `SETTINGS BLOCK` printed them — each line is a setting name, one tab, then the link. Put them in a plain fenced code block so the tabs survive copying. Do not put them in a table or add borders.

````
Add the Drive folders to your planning sheet:

1. Open the planning sheet. If there is no Settings tab, run Planning → Set up sheet first.
2. On the Settings tab, click cell A2 and paste the block below.
   The names land in A2–A4 and the links in B2–B4.
3. Check each link sits next to its matching name in column A.

```
projects_folder	https://drive.google.com/drive/folders/<id>
allocations_folder	https://drive.google.com/drive/folders/<id>
timesheets_folder	https://drive.google.com/drive/folders/<id>
```

Upload the weekly Zoho timesheet xlsx to the timesheets folder, then use Planning → Sync allocation after each export.
````

   (The user can print the block again later with `<py> <skill_dir>/scripts/workspace.py settings-block`.)

6. Re-run `workspace.py check`. If `ready` is still `false`, show what is missing and stop.

### 0d — Read config

Read `config.json`. Take `pm_filter` and `drive.projects_folder_id`.

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
- **Pagination:** if a page holds exactly 100 projects, fetch `page: 2`, `3`, … with the same `per_page` until a page holds fewer than 100. Keep every page's path. (The response has no `page_info`; to count projects in a saved file without reading it into the conversation, run `<py> <skill_dir>/scripts/workspace.py count-projects <path>`.)

If the call fails, print the error and stop.

---

## Step 3 — Build the CSV

Run from the workspace, passing every page's path:

```bash
<py> <skill_dir>/scripts/build_projects.py --month <target_month> <page1_path> [<page2_path> ...]
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

If the upload succeeds, delete this run's local files: the CSV and any `tmp/projects_list_p*.json` from Step 2. Delete only these files, not the whole `tmp/` folder, which may hold an `/actuals-snapshot` partial run. The helper removes `tmp/` itself if it is then empty:

```bash
<py> <skill_dir>/scripts/workspace.py clean <csv filename> "projects_list_p*.json"
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
Drive:  <viewUrl of the uploaded file, or "upload failed">
```

---

## Error handling

- Project list call fails → print error, stop.
- Script exits with an error → print it, stop. Do not build the CSV by hand.
- `tmp/` folder does not exist → created by the script.
- `config.json` missing or incomplete → handled by Step 0c setup; never guess names or folder IDs.

---

## Data integrity rules

- Every value must come from the `get_projects_list` response(s) fetched in this run.
- Never reuse data from memory, conversation history, or prior runs.
- Never hardcode or approximate any field value.
