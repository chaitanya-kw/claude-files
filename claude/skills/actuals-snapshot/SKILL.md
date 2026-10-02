---
description: Export per-person allocated hours from Zoho Projects. Builds the project list from one get_projects_list call, reads people.csv, flags unknown people for resolution, then builds YYYY_MM_DD_HHMM_allocations.csv in tmp/, uploads it to Google Drive and deletes the local copy. Logged hours are not exported — they come from the weekly timesheet xlsx read by the planning sheet. Records MCP responses in a tmp file as they arrive so a compacted or interrupted run can resume.
---

# Zoho Allocations Snapshot Export

Export per-person **allocated** hours from Zoho Projects, build `YYYY_MM_DD_HHMM_allocations.csv` in `tmp/`, and upload it to the Drive allocations folder. Nothing is kept locally: Drive holds the exports.

Logged hours are **not** part of this export. The planning sheet's Apps Script computes them from the weekly Zoho timesheet xlsx, which is per person per day and therefore exact for the month.

---

## Invocation

```
/actuals-snapshot [month]
```

`month` is optional. Examples: `Jun 2026`, `June 2026`, `2026-06`, `this month`.

If no argument is supplied, default to the **current calendar month** using the system date — do not ask.

---

## Constants

- Portal ID: `60037513197`
- MCP tool prefix: `mcp__claude_ai_Zoho_Projects__`
- Batch size for parallel task fetches: 5 projects at a time
- Unassigned owner zpuids to exclude: `0`, `282451000000055461`
- Partial run file: `tmp/actuals_partial.ndjson`
- Config: `config.json` in the repo root — `drive.allocations_folder_id` is the upload target
- Processing script: `scripts/process_actuals.py` in this skill directory

---

## Step 1 — Resolve target month

Derive from argument or system date:

- `target_month` — `YYYY-MM`
- `month_start` — first day as a date
- `month_end` — last day as a date

Print: `Target month: <target_month>`

---

## Step 2 — Build the project list

Projects CSVs are no longer kept in the repo, so build the list the same way `/project-snapshot` does, with the same filters and PM names:

1. Call `mcp__claude_ai_Zoho_Projects__get_projects_list` with `path_variables` `{"portal_id": "60037513197"}` and `query_params` `{"per_page": 100}`. The response is saved to a file; **do not read it**. If a page holds exactly 100 projects, fetch further pages (see `/project-snapshot` Step 2).
2. Build the CSV into `tmp/` with the project-snapshot script:

```bash
mkdir -p tmp && python3 ~/.claude/skills/project-snapshot/scripts/build_projects.py --month <target_month> <page1_path> [<page2_path> ...]
```

The last printed line is the CSV path (`tmp/YYYY_MM_DD_HHMM_projects.csv`). Parse it. Extract per row:

- `project_id`
- `project_name`

This becomes `projectList[]`. Include every row — do not filter any out.

If the list call or the script fails, print the error and stop.

Print: `Source snapshot: <filename>  (N projects)`

---

## Step 3 — Check for partial run

Check whether `tmp/actuals_partial.ndjson` exists.

If it exists, read it. Each line is one project record (see Step 4b for the shape). Extract the set of `project_id` values already present — these are `fetchedIds`. A record may reference saved response files via `tasks_file` / `tasks_files`; check those paths still exist. If any are missing, treat that project as not fetched.

Also check that every `project_id` in `fetchedIds` is still present in `projectList[]`. If any fetched project is no longer in the current projects CSV, warn the user but do not discard its data — include it in processing.

If the partial file exists, **pause and ask**:

```
Partial run found — <N> of <total> projects already fetched.
Resume from where it left off? (yes / no)
```

- If **yes**: proceed to fetch only the remaining projects. Skip to Step 4a.
- If **no**: delete `tmp/actuals_partial.ndjson`. Proceed with a full fresh fetch. Skip to Step 4b.

If no partial file exists, proceed to Step 4b.

---

## Step 4a — Resume fetch (partial run exists)

Create a `remainingList[]` of projects in `projectList[]` whose `project_id` is NOT in `fetchedIds`.

Print: `Resuming — <N already fetched> fetched, <N remaining> remaining.`

Fetch tasks for `remainingList[]` using the same procedure as Step 4b. Append each completed project record to `tmp/actuals_partial.ndjson` as it completes.

Proceed to Step 5.

---

## Step 4b — Full fetch

Create `tmp/` folder if it does not exist.

Create (or overwrite) `tmp/actuals_partial.ndjson` as an empty file before fetching begins.

For each project in `projectList[]`, call `mcp__claude_ai_Zoho_Projects__get_tasks_by_project`:

- `path_variables`: `{"portal_id": "60037513197", "project_id": "<project_id>"}`
- `query_params`:
  - `per_page`: 200
  - `filter`: the month filter below, with `<month_start>` / `<month_end>` as `YYYY-MM-DD`

```json
{"criteria":[
  {"field_name":"start_date","criteria_condition":"less_than_or_equal","value":["<month_end>"]},
  {"field_name":"end_date","criteria_condition":"greater_than_or_equal","value":["<month_start>"]},
  {"field_name":"start_date","criteria_condition":"is","value":["${unscheduled}"]},
  {"field_name":"status","criteria_condition":"is","value":["${all_open}"]}
],"pattern":"(1 AND 2) OR (3 AND 4)"}
```

This returns tasks overlapping the month, plus undated tasks that are still open. Undated closed tasks are excluded: they carry no allocation and previously made up most of each response. Pass `filter` as a JSON **string**. The pattern must use uppercase `AND` / `OR`. `is_empty` is rejected on date fields — use the `${unscheduled}` macro as shown.

**Issue in batches of 5 simultaneous calls.** Wait for all 5 to complete before starting the next batch.

**Pagination:** If `page_info.has_next_page` is `true`, fetch page 2, 3, etc. until exhausted.

**Rate limiting:** HTTP 429 → wait and retry. Do not skip. Inform the user if the wait exceeds 10 seconds.

### Recording each project — do not copy raw JSON

After each project's fetch completes (all pages), immediately append **one line** to `tmp/actuals_partial.ndjson`. How depends on how the response arrived:

**Response saved to a file** (the tool result says the output was saved to a path): reference the file — never read or re-emit its contents.

```json
{"project_id": "...", "project_name": "...", "fetched_at": "<IST ISO datetime>", "pages_fetched": 1, "tasks_files": ["<saved path>"]}
```

With several pages, list every page's saved path in `tasks_files`.

**Response returned inline:** write a slim record containing only these fields per task — nothing else:

```json
{"project_id": "...", "project_name": "...", "fetched_at": "...", "pages_fetched": 1, "tasks": [
  {"start_date": "...", "end_date": "...",
   "owners_and_work": {"work_type": "...", "total_work": "HH:MM",
     "owners": [{"zpuid": "...", "name": "...", "email": "...", "work_values": "..."}]}}
]}
```

Omit `start_date` / `end_date` when the task has none. Keep `work_values` exactly as returned (string, or the list of date entries for flexible tasks). A project whose pages arrived in mixed forms can carry both `tasks_files` and `tasks`. When `tasks_files` is present it takes precedence, so put inline pages' tasks into a separate record line with the same `project_id`.

A project with zero tasks still gets a record with `"tasks": []`.

Track: `paginatedProjects[]`, `failedProjects[]`.

Print progress after each batch: `Fetched <N>/<total> projects...`

Print when all fetches complete: `All task data fetched. Checking people...`

---

## Step 5 — Find unknown people

Run from the repo root:

```bash
python3 <skill_dir>/scripts/process_actuals.py --month <target_month> --check-people
```

It prints a JSON list of `{zpuid, name, email}` for owners of in-month tasks whose zpuid is not in `people.csv`. It reads saved response files itself, so the task data never needs to come through the conversation.

---

## Step 6 — Resolve people.csv

`people.csv` columns: `person_name`, `person_zpuid`, `person_email`, `team`. Re-read it fresh.

If Step 5 returned anyone, **pause and present them**:

```
Unknown people found in task data — not in people.csv:

  zpuid                 name (as returned by Zoho)     email
  ──────────────────────────────────────────────────────────────
  282451000001234567    John Smith                     john.smith@…
  282451000009876543    jane.doe                       jane.doe@…

For each person, reply with:
  team   — add to people.csv with team = true
  other  — add to people.csv with team = false
  skip   — exclude from this run (do not add to people.csv)

Reply in the format:
  <zpuid>: team|other|skip
```

Wait for the user's response. Do not proceed until all unknowns are resolved.

Once the user replies:

- `team` or `other`: append a row to `people.csv` with `person_name` (Zoho-returned name), `person_zpuid`, `person_email`, `team` = `true` or `false`.
- `skip`: not added to `people.csv`. Pass these zpuids to Step 7 with `--skip`.
- Re-read `people.csv` after writing to confirm rows were appended correctly.

If there are no unknown people, continue without pausing.

Print: `people.csv resolved. Processing allocations...`

---

## Step 7 — Process allocations

```bash
python3 <skill_dir>/scripts/process_actuals.py --month <target_month> [--skip <zpuid>,<zpuid>]
```

Run from the repo root. The script:

- reads `tmp/actuals_partial.ndjson` (inline tasks and saved response files) and `people.csv`;
- keeps tasks overlapping the month (undated tasks count as active);
- computes each owner's allocation (rules below);
- backfills empty `person_email` values in `people.csv` from task owner data;
- writes `tmp/YYYY_MM_DD_HHMM_allocations.csv`;
- prints a summary. **The last printed line is the CSV path.**

If the script is unavailable, apply the rules below manually.

### Hour string conversion

```
"08:00" → 8.0
"21:30" → 21.5
"00:00" → 0.0
"" / null → 0.0
```

### Owner allocation

Zoho supports three ways to set a task's `work_values` per owner — Total hours, Work hours/day, and Work %/day — but `owners_and_work.work_type` only ever holds `"standard"` or `"flexible"`. The allocation is derived unit-agnostically:

- `owners_and_work.total_work` is always the task-level total, computed by Zoho for whatever unit was actually used.
- Each owner's `work_values` is their **share of `total_work`**, not necessarily an absolute total.

```
raw_value(owner) = decimal(owner.work_values)
raw_sum           = sum(raw_value(owner) for all owners on the task, including excluded/unassigned)
allocated(owner)  = raw_value(owner) * decimal(total_work) / raw_sum      # if raw_sum > 0
                   = 0.0                                                  # if raw_sum == 0
```

**Flexible work_type**: `work_values` is an array of `{"date": "YYYY-MM-DD", "value": "HH:MM"}` entries (or `{"day": N, ...}` — rare, included as-is). Sum the owner's own entries whose `date` falls within the month. Do not redistribute `total_work` for flexible tasks.

Skip zpuids `0` and `282451000000055461`.

### Aggregation

Aggregate `allocated_hours` per `(project_id, zpuid)` across all included tasks.

---

## Step 8 — CSV columns

Sorted by `project_name`, then `person_name`. One row per `(project_id, zpuid)`.

| Column            | Value                         |
| ----------------- | ----------------------------- |
| `project_id`      | project ID                    |
| `project_name`    | project name                  |
| `person_name`     | name from `people.csv`        |
| `person_zpuid`    | owner zpuid                   |
| `person_email`    | from `people.csv`, else Zoho  |
| `allocated_hours` | decimal, 2dp                  |
| `export_month`    | `target_month` in `YYYY-MM`   |

---

## Step 9 — Upload to Drive

Read `drive.allocations_folder_id` from `config.json`. Read the CSV written in Step 7 and call `mcp__claude_ai_Google_Drive__create_file`:

- `title`: the CSV filename (e.g. `2026_10_02_1443_allocations.csv`)
- `parentId`: `drive.allocations_folder_id`
- `textContent`: the CSV file contents, exactly as written
- `contentMimeType`: `text/csv`
- `disableConversionToGoogleType`: `true`

If the upload fails, report it and **do not** delete `tmp/`: the CSV there is the only copy. Ask the user whether to retry. Otherwise the run is complete.

Then delete the partial file and the `tmp/` folder:

```bash
rm -rf tmp/
```

---

## Step 10 — Print summary

```
Run complete — <target_month>
Source snapshot:          <filename>
Projects processed:       <N>
Unique people:            <N>
New people added:         <N> — <names if any>
Skipped people:           <N> — <names if any>
Emails backfilled:        <N>
People missing email:     <N> — <names if any>
Zero allocated hours:     <N> — <names if any>
Paginated fetches:        <N> — <names if any>
Fetch failed:             <N> — <names if any>
Drive:  <viewUrl of the uploaded file, or "upload failed">
```

---

## Error handling

- Project list call or `build_projects.py` fails → print error, stop. Do not delete partial file.
- Projects CSV missing `project_id` or `project_name` → print error, stop. Do not delete partial file.
- `people.csv` not found → print error, stop. Do not delete partial file.
- `people.csv` missing required columns (`person_name`, `person_zpuid`, `team`) → print error, stop. A missing `person_email` column is added by the script.
- `config.json` missing or without `drive.allocations_folder_id` → skip the upload, say so in the summary.
- Task fetch fails after one retry → write a record with `"tasks": []` and `"fetch_failed": true`. Flag in summary.
- Filter rejected with HTTP 400 → print the error. Do not fall back to an unfiltered fetch without asking: unfiltered responses are roughly 15× larger.
- Any stop due to error → leave `tmp/actuals_partial.ndjson` in place so the run can be resumed once the issue is resolved.

---

## Data integrity rules

- Every hours value must come from a live API response in this run or a partial file written during this run.
- Never reuse data from memory or conversation history — the partial file and the saved response files it references are the only valid state store.
- Never skip a project's task fetch regardless of engagement model or expected zero-hours status.
- Never approximate or reconstruct hours from any source other than raw task API responses.
- `people.csv` is the sole source of truth for canonical names — always re-read it fresh, never rely on memory.
- If data cannot be retrieved after retrying, output empty hours and flag it. Do not substitute.
