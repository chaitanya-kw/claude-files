---
name: progress-review
description: Compare a task list against the codebase to estimate project completion. On the first run, reads progress-reports/initial-tasks.csv. On subsequent runs, auto-locates the previous run's output CSV. Uses CLAUDE.md for project context. Produces a weighted completion report and an output CSV that serves as the ideal input for the next run. Tracks scope changes against initial-tasks.csv across all runs. Supports incremental runs — previously evaluated tasks are carried forward by id. All outputs are written to a timestamped subfolder under progress-reports/.
allowed-tools: Read, Glob, Grep, Bash
disable-model-invocation: true
---

## Token optimisation

Before starting, note the session token count. After each `/compact` call, record
tokens before and after. Write the delta to `${OUTPUT_DIR}/token-usage.md` at the end
of the run using the structure in Phase 9.

Run `/compact` at these points:
- After Phase 2 (incremental matching complete, full CSV history no longer needed)
- After Phase 5 (code evaluation complete, grep output no longer needed)

---

## Usage

```
/project:progress [<path-to-csv>] [--baseline] [--recheck] [--since <subfolder-or-csv-path>]
```

- `<path-to-csv>` — optional. Path to a `.csv` task file. If omitted, resolution
  follows the rules in Phase 0b.
- `--baseline` — optional. Marks this run as a deliberate scope baseline snapshot.
  Sets `Baseline: true` in all output. Can be combined with `--recheck`.
- `--recheck` — optional. Forces full re-evaluation of all tasks, ignoring carried-forward
  results from any previous run.
- `--since <subfolder-or-csv-path>` — optional. Path to a specific previous output subfolder
  (e.g. `progress-reports/20250317_1430`) or a direct CSV path to use as the incremental
  baseline. Ignored if `--recheck` is passed.

---

## CSV format

One format only. All columns are accepted on input and written on output.
The output CSV from any run is a valid input for the next run — no transformation needed.

| Column              | Required on input    | Written on output | Notes |
|---------------------|----------------------|-------------------|-------|
| `id`                | No¹                  | Yes               | Stable identifier for incremental matching. |
| `task`              | Yes                  | Yes               | Task description. |
| `type`              | Yes                  | Yes               | `code` or `non-code`. |
| `status`            | For non-code tasks   | Yes               | `done`, `in-progress`, `blocked`, `not-started`. For code tasks, written by the evaluator. |
| `weight`            | No                   | Yes               | Numeric 1–5. User-provided values are preserved. LLM-assigned values are written for future runs. |
| `group`             | No                   | Yes               | Optional grouping label. |
| `notes`             | No                   | Yes               | Free text. |
| `confidence`        | No²                  | Yes               | `high`, `medium`, `low`, or `—` for non-code tasks. |
| `done_pct`          | No²                  | Yes               | Numeric 0–100. Completion percentage for this task. |
| `ambiguity_reason`  | No²                  | Yes               | Populated when status is `ambiguous`. Blank otherwise. |
| `weight_rationale`  | No²                  | Yes               | Populated when weight was LLM-assigned. Blank for user-provided weights. |
| `grep_hits`         | No²                  | Yes               | Semicolon-separated list of `file:line` hits from the last evaluation. Reused on incremental re-evaluation to skip redundant grep searches. |
| `source`            | No²                  | Yes               | `fresh`, `carried`, or `recheck`. |

¹ If `id` is absent, incremental matching is disabled for this run.
² These columns are output-only on the first run. On subsequent runs they are read back
  as part of incremental matching and preserved or updated as appropriate.

---

## Phase 0 — Locate and validate input

### 0a. Establish output subfolder

Generate the IST timestamp for this run before any other work:

```bash
AUDIT_TS=$(TZ='Asia/Kolkata' date +%Y%m%d_%H%M)
OUTPUT_DIR="progress-reports/${AUDIT_TS}"
mkdir -p "${OUTPUT_DIR}"
echo "Output dir: ${OUTPUT_DIR}"
```

All files written this run go into `${OUTPUT_DIR}`.

Determine the `IS_BASELINE` flag for this run:
- If `--baseline` was passed: `IS_BASELINE=true`
- If this is the first run (detected in Phase 0b step 3): `IS_BASELINE=true`
- Otherwise: `IS_BASELINE=false`

### 0b. Resolve input file

Apply this resolution order:

1. If `<path-to-csv>` was provided: use it. Verify the file exists.

2. If `--since <subfolder-or-csv-path>` was provided:
   - If the path ends in `.csv`, use it directly. Verify it exists.
   - If the path is a directory (e.g. `progress-reports/20250317_1430`), locate the
     `.csv` file inside it:
     ```bash
     ls <subfolder>/*-tasks.csv 2>/dev/null | head -1
     ```
   - Print:
     ```
     Using --since baseline: <resolved csv path>
     ```

3. **First-run check**: look for `progress-reports/initial-tasks.csv`:
   ```bash
   ls progress-reports/initial-tasks.csv 2>/dev/null
   ```
   Check whether any output CSVs from previous runs exist:
   ```bash
   ls progress-reports/*/*-tasks.csv 2>/dev/null | head -1
   ```
   - If `initial-tasks.csv` exists **and no previous run output exists**: this is the
     first run. Use `progress-reports/initial-tasks.csv` as input. Set `IS_BASELINE=true`.
     Print:
     ```
     First run detected. Using: progress-reports/initial-tasks.csv
     ```
   - If `initial-tasks.csv` exists **and previous run outputs also exist**: auto-locate
     the most recent output CSV (step 4 below).
   - If `initial-tasks.csv` does not exist: proceed to step 4.

4. Auto-locate: find the most recent output CSV across all subfolders in `progress-reports/`:
   ```bash
   ls progress-reports/*/*-tasks.csv 2>/dev/null | sort | tail -1
   ```
   If found, print:
   ```
   No input file specified. Using most recent output: <resolved csv path>
   ```

If no file can be resolved by any of the above strategies, print:

```
No task file found.
  - Add an initial task list:     progress-reports/initial-tasks.csv
  - Pass a CSV path:              /project:progress tasks/my-tasks.csv
  - Pin a previous run:           /project:progress --since progress-reports/20250317_1430
  - Or let me create an empty task list CSV with the correct format for you to fill in.

Create the empty CSV? (yes / no)
```

Wait for the user's response. If yes, write `${OUTPUT_DIR}/tasks-template.csv` with
all columns as headers and no data rows, then stop. If no, stop.

**Important:** `progress-reports/initial-tasks.csv` is never overwritten or deleted
by this command. It is a read-only baseline for scope tracking across all runs.

### 0c. Parse and validate

1. Parse the CSV into a normalised internal list:

```
[
  { id, task, type, status, weight, group, notes,
    confidence, done_pct, ambiguity_reason, weight_rationale, source }
]
```

2. Check for `id` column. If absent, print:
   ```
   NOTE: No 'id' column found. Incremental matching disabled — all tasks will be evaluated fresh.
   ```

3. Validate:
   - Every row has a non-empty `task`.
   - Every row has `type` of `code` or `non-code`.
   - Non-code rows have a valid `status` value.
   - `weight` if present is a positive number.

4. On any validation error, print the offending row number and stop:
   ```
   ERROR: Row 4 — missing required value in 'type' column.
   Fix the CSV and re-run.
   ```

---

## Phase 1 — Load project context

Read `CLAUDE.md` from the project root. Extract:

- `## Project` — domain and purpose summary
- `## Stack` — languages and frameworks in use
- `## Architecture` — key directories and patterns
- `## Business logic` — domain entities and rules
- `## Audit Config` — `src_dirs`, `exclude_dirs`, and optionally `progress_file_cap`

If `CLAUDE.md` does not exist, warn and continue:

```
WARNING: CLAUDE.md not found. Run /project:init-claude-md first for better accuracy.
Proceeding with defaults.
```

### File read cap

Resolve in this priority order:

1. `progress_file_cap` from `## Audit Config` — use as-is if present.
2. Task list length:

| Task count | Cap |
|------------|-----|
| ≤ 20       | 40  |
| 21–50      | 80  |
| 51–100     | 140 |
| > 100      | 200 |

Record the resolved cap and its source for the dry-run output.

Set `SRC_DIRS` and `EXCLUDE_DIRS` from Audit Config or defaults:
- `SRC_DIRS` default: `src,app,lib,api,server,services,handlers,controllers,utils`
- `EXCLUDE_DIRS` default: `node_modules,.next,.nuxt,dist,build,bin,obj,coverage,.git,__pycache__`

---

## Phase 2 — Incremental task resolution

Skip entirely if `--recheck` was passed or no `id` column was found in Phase 0.

### 2a. Explicit input file — treat as source of truth

If the input was provided as an explicit path (not auto-located and not `--since`),
the user may have manually edited any column to improve accuracy.

The input file is the starting state. Do not merge or reconcile against any previous
run's output. All column values in the file are accepted as-is, including any user
corrections to `weight`, `status`, `confidence`, `done_pct`, or `ambiguity_reason`.

If the user has updated a task description and wants it re-evaluated, they are
responsible for clearing `status`, `ambiguity_reason`, and any other evaluation
fields in the CSV. The command re-evaluates any task where those fields are blank —
no description comparison is performed.

### 2b. Carry-forward rules

For each task that has an `id` and has not been flagged for re-evaluation in 2a:

Carry forward if **all** of the following are true:
- `status`, `confidence`, and `done_pct` are populated.
- `source` is not `recheck`.
- `status` is `done` **and** `confidence` is `high`.

Queue for re-evaluation if **any** of the following are true:
- `status` is not `done` (i.e. `partial`, `not-started`, `ambiguous`).
- `confidence` is `medium` or `low`.
- `source` is `recheck`.
- Evaluation fields are blank or absent.

For tasks being carried forward:
- Preserve all evaluation fields as-is.
- `weight` from the current file takes precedence over any carried value.
- Mark `source=carried` on output.

For tasks queued for re-evaluation:
- Preserve `task`, `type`, `group`, `notes`, `weight` (current file is source of
  truth for these).
- Clear `status`, `confidence`, `done_pct`, `ambiguity_reason` — these will be
  rewritten by Phase 5 or 6.
- Mark `source=fresh` on output.

Print a match summary:

```
Incremental matching:
  Carried forward (done + high confidence):  12 tasks
  Re-evaluating  (incomplete or uncertain):   6 tasks
  Re-evaluating  (ambiguous, desc updated):   1 task
  Fresh (no prior result):                   15 tasks
  Total to evaluate this run:                22 tasks
```

### 2c. Scope tracking against initial-tasks.csv

If `progress-reports/initial-tasks.csv` exists and the current input is not itself
`initial-tasks.csv` (i.e. this is not the first run), read `initial-tasks.csv` and
compute the scope diff.

Match tasks by `id` if present in both files. Fall back to exact `task` string match
if `id` is absent.

Compute:
- **Added tasks**: present in current input, absent from initial list (by id or task string).
- **Removed tasks**: present in initial list, absent from current input.
- **Initial total weight**: sum of all `weight` values in `initial-tasks.csv`.
  For any task in `initial-tasks.csv` with a blank weight, use the LLM-assigned weight
  from the current run if available; otherwise use 3 as the default.
- **Current total weight**: sum of all `weight` values in the current input (same
  fallback rules apply).
- **Weight delta**: current total weight minus initial total weight.

Store this data for use in the report (Phase 8b) and dry run (Phase 4).
Do not print the full diff here — print only a one-line summary:

```
Scope tracking: +<n> added, -<n> removed vs initial-tasks.csv  (weight delta: <+/->N pts)
```

If `initial-tasks.csv` does not exist, print:
```
Scope tracking: initial-tasks.csv not found — scope section will be omitted from report.
```

---

## Phase 3 — Assign weights

### 3a. Partition tasks

Before any estimation, split all tasks into two buckets:

- **skip**: `weight` is already a numeric value in the input CSV. Accept as-is. Set `weight_rationale` to blank. Do not re-examine or re-reason about these tasks.
- **needs-weight**: `weight` is blank or absent.

Print the partition summary:

```
Weight assignment:
  Pre-weighted (skipped):  18 tasks  — user-provided values preserved
  Needs assignment:         4 tasks
```

If `needs-weight` is empty, skip Phase 3 entirely and proceed to Phase 4.

### 3b. Estimate weights for needs-weight tasks

Estimate on a **1–5 scale**:

| Weight | Meaning |
|--------|---------|
| 1 | Trivial — config change, copy update, single-function fix |
| 2 | Small — well-scoped single feature or bug with clear boundaries |
| 3 | Medium — multi-file change, moderate integration work |
| 4 | Large — significant feature, cross-cutting concern, or external integration |
| 5 | Complex — architectural change, ambiguous scope, or high-risk area |

Base estimates on the task description, domain context from `CLAUDE.md`, and the stack.
Record a one-line rationale in `weight_rationale` for every LLM-assigned weight.

---

## Phase 4 — Dry run (always executed)

Print before any codebase reads begin. Do not wait for confirmation — proceed immediately.
The user may interrupt if they disagree with weights or carry-forwards.

```
===========================================================
DRY RUN — /project:progress
===========================================================
Input CSV:       progress-reports/20250317_1430/20250317_1430-tasks.csv  [auto-located]
Output dir:      progress-reports/20250324_1615/
Baseline:        false  (pass --baseline to mark this run as a scope snapshot)
Total tasks:     34  (21 code, 13 non-code)
Groups:          Payments, Auth, Notifications, Infra
ID matching:     YES
                   Carried forward (done + high confidence):  12
                   Re-evaluating   (incomplete or uncertain):   6
                   Fresh (no prior result):                    16
Tasks to eval:   22 total
File read cap:   80  (source: task-count fallback — 34 tasks → tier 21–50)
Est. token cost: ~14 000 input  (22 tasks × ~5 files × ~120 tokens/file avg)
Mode:            INCREMENTAL  (pass --recheck to re-evaluate all tasks)
Scope vs initial: +3 added, -1 removed  (weight delta: +5 pts)

WEIGHT ASSIGNMENTS (tasks to be evaluated this run)
-----------------------------------------------------------
 #   ID         Task                                  W   Rationale
---  ---------  ------------------------------------  --  -----------------------------------
 1   pay-2      Refund flow                           3*  Multi-step, touches payments + ledger
 2   auth-2     OAuth provider integration            4*  External integration, moderate risk
 3   notif-1    Email notification on order dispatch  2*  Single-purpose, well-scoped
...

* = LLM-assigned

CARRIED-FORWARD TASKS
-----------------------------------------------------------
 #   ID         Task                           Status    Conf    Done%
---  ---------  -----------------------------  --------  ------  -----
 5   pay-1      Stripe webhook handler         done      high    100%
 7   auth-1     JWT middleware                 done      high    100%
...

Proceeding to codebase evaluation...
===========================================================
```

---

## Phase 5 — Evaluate code tasks

Only `type: code` tasks that are not carried-forward are evaluated here.
Prioritise by descending weight. Track total file reads against the cap.
If the cap is reached, mark remaining unevaluated tasks `ambiguous` with
`ambiguity_reason` = "file cap reached".

### 5a. Pre-search: reuse cached grep hits

Before running any grep commands, check each task's `grep_hits` field from the input CSV.

- If `grep_hits` is populated **and** the task's prior `confidence` was `medium`:
  - Parse the semicolon-separated `file:line` list.
  - Verify each file still exists on disk (`find <file> -maxdepth 0`).
  - If all files exist: skip to 5b using these hits directly. Do not run grep.
  - If any file is missing: discard the cached hits and run a fresh search in 5a-1.
- If `grep_hits` is blank, or prior `confidence` was `low` or absent: run a fresh search.
- If prior `confidence` was `high`: this task should have been carried forward in Phase 2.
  If it reaches Phase 5, treat as fresh.

Print a pre-search summary before beginning evaluation:

```
Grep cache:
  Reusing cached hits (medium confidence, files verified):   5 tasks  — grep skipped
  Fresh search required (low/blank confidence or missing):  17 tasks
```

### 5a-1. Targeted search (fresh tasks only)

For each task requiring a fresh search:

1. Extract 2–4 keywords from the task description.
2. Grep across `SRC_DIRS`:

```bash
grep -rn \
  $(echo "$EXCLUDE_DIRS" | tr ',' '\n' | sed 's/^/--exclude-dir=/' | tr '\n' ' ') \
  --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
  --include="*.py" --include="*.go" --include="*.rs" \
  <keywords> <src_dirs>
```

3. Use Glob for file patterns implied by the task description.
4. Store the top grep hits (up to 10 `file:line` entries) in `grep_hits` as a
   semicolon-separated string for use in future runs.

### 5b. Read and assess

Read up to 5 files per task from grep/glob hits or cached hits, counted against the global cap.

| Field       | Values |
|-------------|--------|
| `status`    | `done`, `partial`, `not-started`, `ambiguous` |
| `confidence`| `high`, `medium`, `low` |
| `done_pct`  | `done`=100, `partial`=50 (±20 based on evidence), `not-started`=0, `ambiguous`=30 |

If the task is too vague to grep for meaningfully, mark it `ambiguous` immediately
and populate `ambiguity_reason`. No files read. Clear `grep_hits`.

Run `/compact` after all code tasks are evaluated.

---

## Phase 6 — Evaluate non-code tasks

For non-code tasks not carried-forward, map `status` to `done_pct`:

| Status       | done_pct |
|--------------|----------|
| `done`       | 100      |
| `in-progress`| 50       |
| `blocked`    | 25       |
| `not-started`| 0        |

Set `confidence` to `—`. No file reads.

---

## Phase 7 — Calculate completion

For each task:

```
task_score = weight × (done_pct / 100)
```

Aggregate at the group level and at the project level. For each group (or `_project`
if no groups exist), compute all of the following. Retain decimal precision — do not
round scores to integers.

**Scores (decimal):**
```
current_score          = sum of task_score for all tasks in group
max_score              = sum of weight for all tasks in group
current_code_score     = sum of task_score for code tasks in group
max_code_score         = sum of weight for code tasks in group
current_non_code_score = sum of task_score for non-code tasks in group
max_non_code_score     = sum of weight for non-code tasks in group
```

**Task counts (integer):**
```
tasks_done_total        = count where done_pct == 100
tasks_done_code         = count where done_pct == 100 and type == code
tasks_done_non_code     = count where done_pct == 100 and type == non-code
tasks_partial_total     = count where done_pct > 0 and done_pct < 100 and status != ambiguous
tasks_partial_code      = same, code only
tasks_partial_non_code  = same, non-code only
tasks_not_started_total = count where done_pct == 0 and status != ambiguous
tasks_not_started_code  = same, code only
tasks_not_started_non_code = same, non-code only
ambiguous_code          = count where status == ambiguous and type == code
ambiguous_non_code      = count where status == ambiguous and type == non-code
```

**Derived percentages (for human display only — not stored by the dashboard):**
```
pct_complete          = (current_score / max_score) × 100
pct_code_complete     = (current_code_score / max_code_score) × 100
pct_non_code_complete = (current_non_code_score / max_non_code_score) × 100
```

Compute for: all groups individually, and a project-level rollup (sum across all groups).

---

## Phase 8 — Write outputs

Both files use the same IST timestamp as the `${OUTPUT_DIR}` subfolder established
in Phase 0a. Write both files into `${OUTPUT_DIR}`.

### 8a. Output CSV

Write to `${OUTPUT_DIR}/<YYYYMMDD_HHMM>-tasks.csv`.

Include every task — carried-forward and freshly evaluated.
Column order must match the format table in the CSV Format section exactly.
This file is the canonical input for the next run.

### 8b. Report

Write to `${OUTPUT_DIR}/<YYYYMMDD_HHMM>-progress-report.md`.

The report must use **exactly** the section headers, sub-section headers, and
table column names shown below. The dashboard parser matches these literals.

```markdown
# Progress Report — <project name from CLAUDE.md>

**Date:** <YYYY-MM-DD HH:MM IST>
**Mode:** INCREMENTAL — <n> tasks carried from <input subfolder> | FULL (--recheck)
**Baseline:** <true | false>
**Tasks:** <n> total (<x> code, <y> non-code)

---

## Overall Completion

### Scores

| Metric                   | Value |
|--------------------------|-------|
| Current Score            | <decimal> |
| Max Score                | <decimal> |
| % Complete               | <n>%  |
| Current Code Score       | <decimal> |
| Max Code Score           | <decimal> |
| % Code Complete          | <n>%  |
| Current Non-Code Score   | <decimal> |
| Max Non-Code Score       | <decimal> |
| % Non-Code Complete      | <n>%  |

### Tasks

| Metric                     | Value |
|----------------------------|-------|
| Total Tasks Done           | <n>   |
| Code Tasks Done            | <n>   |
| Non-Code Tasks Done        | <n>   |
| Total Tasks Partial        | <n>   |
| Code Tasks Partial         | <n>   |
| Non-Code Tasks Partial     | <n>   |
| Total Tasks Not Started    | <n>   |
| Code Tasks Not Started     | <n>   |
| Non-Code Tasks Not Started | <n>   |
| Ambiguous Code Tasks       | <n>   |
| Ambiguous Non-Code Tasks   | <n>   |

---

## Group Breakdown

*(When no groups exist, emit a single row with Group = `_project` in both tables below.)*

### Scores

| Group | Current Score | Max Score | % Complete | Current Code Score | Max Code Score | % Code Complete | Current Non-Code Score | Max Non-Code Score | % Non-Code Complete |
|-------|---------------|-----------|------------|--------------------|----------------|-----------------|------------------------|--------------------|---------------------|
| <group> | <decimal> | <decimal> | <n>% | <decimal> | <decimal> | <n>% | <decimal> | <decimal> | <n>% |

### Tasks

| Group | Total Done | Code Done | Non-Code Done | Total Partial | Code Partial | Non-Code Partial | Total Not Started | Code Not Started | Non-Code Not Started | Ambiguous Code | Ambiguous Non-Code |
|-------|------------|-----------|---------------|---------------|--------------|------------------|-------------------|------------------|----------------------|----------------|--------------------|
| <group> | <n> | <n> | <n> | <n> | <n> | <n> | <n> | <n> | <n> | <n> | <n> |

---

## Scope Tracking

*(Omit this section entirely if `progress-reports/initial-tasks.csv` does not exist
or if the current run is itself the first run against `initial-tasks.csv`.)*

| Metric                  | Initial | Current | Delta |
|-------------------------|---------|---------|-------|
| Total tasks             |         |         |       |
| Total weight (points)   |         |         |       |

### Added tasks
*(Tasks present in current list but absent from `initial-tasks.csv`)*

| ID | Task | Group | Weight |
|----|------|-------|--------|
|    |      |       |        |

*(Omit table if no tasks were added)*

### Removed tasks
*(Tasks present in `initial-tasks.csv` but absent from current list)*

| ID | Task | Group | Weight |
|----|------|-------|--------|
|    |      |       |        |

*(Omit table if no tasks were removed)*

---

## Ambiguous / Unverifiable Tasks

| #  | ID     | Task | Reason |
|----|--------|------|--------|
| 7  | auth-2 | ...  | Code found but scope unclear — multiple providers referenced |

*(Omit if none)*

---

## Suggested Next Actions

Ordered by weight × incompleteness. Max 7 items.

1. **[TASK]** (weight: 5, 0% complete) — <one-line recommendation>
2. ...

---

## Report Metadata

- Input CSV: <filename>
- Output dir: <path>
- Baseline: <true | false>
- File read cap: <n> (source: <config | task-count fallback>)
- Files read this run: <n>
- Tasks carried forward: <n> (done + high confidence)
- Tasks re-evaluated: <n> (incomplete or uncertain confidence)
- Tasks evaluated fresh: <n>

---

## Token Usage

- Input tokens:  <n>
- Output tokens: <n>
- Total tokens:  <n>

Top consumers:
- Phase <n> — <label>: ~<n> tokens
- Phase <n> — <label>: ~<n> tokens
- Phase <n> — <label>: ~<n> tokens
```

**Notes on the report format:**
- `Baseline` must appear in both the header block and the `## Report Metadata` block
  with the same value. The value is `IS_BASELINE` as resolved in Phase 0a.
- Score values are decimal (e.g. `14.5`, not `14`). Percentages round to one decimal place.
- The `## Overall Completion` tables are always present and serve as a fallback for
  the dashboard when group tables are absent or empty.
- The `## Group Breakdown` tables are always present. When no groups are defined in
  the task list, emit a single row where `Group` is the literal string `_project`
  containing the project-level rollup values.

---

## Phase 9 — Token usage file

Write `${OUTPUT_DIR}/token-usage.md`:

```markdown
# Token Usage — <project name> progress run <AUDIT_TS>

| Phase | Description                          | Tokens (approx) |
|-------|--------------------------------------|-----------------|
| 0–1   | Input resolution + project context   |                 |
| 2     | Incremental matching + scope diff    |                 |
| 3–4   | Weight assignment + dry run          |                 |
| 5     | Code task evaluation                 |                 |
| 6     | Non-code task evaluation             |                 |
| 7–8   | Scoring + report generation          |                 |
| **Total** |                                  | **             ** |

## Compaction savings

| Compaction point      | Tokens before | Tokens after | Saved |
|-----------------------|---------------|--------------|-------|
| After Phase 2         |               |              |       |
| After Phase 5         |               |              |       |

## Notes

- Model: <model>
- Largest phase: Phase <N> — <tokens>
```

---

## Constraints

- Never run the project, install dependencies, or execute tests.
- `Bash` is permitted only for `grep`, `find`, `ls`, `mkdir`, and `wc`.
- Cap at 5 file reads per code task, counted against the global cap.
- Do not read files outside `SRC_DIRS`.
- Tasks too vague to grep for are marked `ambiguous` immediately — no file reads consumed.
- `progress-reports/initial-tasks.csv` is never written to, moved, or deleted.
- `--recheck` and `--since` are mutually exclusive. If both are passed, print:
  ```
  ERROR: --recheck and --since cannot be used together.
  --recheck ignores all previous results. --since pins a specific baseline.
  ```
  Then stop.
- `--baseline` and `--since` may be combined (to mark a pinned-baseline run as a
  scope snapshot). `--baseline` and `--recheck` may also be combined.
