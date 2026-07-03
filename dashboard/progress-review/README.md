# project:progress

Estimates project completion by cross-referencing a structured task list (CSV) against a codebase. Uses weighted scoring, incremental evaluation, and self-chaining runs. Output is compatible with the project dashboard ingestion pipeline.

---

## Installation

### Personal (available in all projects)

```bash
mkdir -p ~/.claude/skills/progress-review
cp SKILL.md ~/.claude/skills/progress-review/
```

### Project-local

```bash
mkdir -p .claude/skills/progress-review
cp SKILL.md .claude/skills/progress-review/
```

Verify it is available in Claude Code:

```
/progress-review
```

---

## Usage

```
/project:progress
/project:progress <path-to-csv>
/project:progress --recheck
/project:progress --since <subfolder-or-csv-path>
/project:progress --baseline
```

| Flag | Effect |
|------|--------|
| (none) | Auto-locates the most recent output CSV, or `progress-reports/initial-tasks.csv` on first run |
| `<path-to-csv>` | Uses the specified CSV as input |
| `--recheck` | Re-evaluates all tasks from scratch, ignoring any carried-forward results |
| `--since <path>` | Uses a specific previous run subfolder or CSV as the incremental baseline |
| `--baseline` | Marks this run as a deliberate scope baseline snapshot (`Baseline: true` in the report) |

`--recheck` and `--since` are mutually exclusive.

---

## Task CSV format

Place your initial task list at `progress-reports/initial-tasks.csv`. This file is never overwritten by the command — it is the permanent scope baseline for scope tracking across all runs.

| Column | Required | Notes |
|--------|----------|-------|
| `id` | No | Stable identifier. Required for incremental matching across runs. |
| `task` | Yes | Task description. |
| `type` | Yes | `code` or `non-code`. |
| `status` | For non-code tasks | `done`, `in-progress`, `blocked`, `not-started`. Written by the evaluator for code tasks. |
| `weight` | No | 1–5. User-provided values are preserved across runs. LLM assigns if blank. |
| `group` | No | Optional grouping label. Used in Group Breakdown tables. |
| `notes` | No | Free text. Carried forward unchanged. |

Output-only columns (`confidence`, `done_pct`, `ambiguity_reason`, `weight_rationale`, `grep_hits`, `source`) are written by the command and carried forward on subsequent runs.

Use the companion **`task-to-progress-csv`** skill to convert an existing task list into this format.

---

## Output

All output is written to a timestamped subfolder: `progress-reports/YYYYMMDD_hhmm/`

| File | Contents |
|------|----------|
| `YYYYMMDD_hhmm-progress-report.md` | Primary report — completion scores, group breakdown, scope tracking, suggested actions |
| `YYYYMMDD_hhmm-tasks.csv` | Full task list with updated evaluation fields. Feed this into the next run. |
| `token-usage.md` | Per-phase token consumption and compaction savings |

---

## CLAUDE.md integration

The command reads `## Audit Config` from `CLAUDE.md` in the project root if present.
Run `/project:init-claude-md` first to generate a `CLAUDE.md` with the correct config block.

Relevant keys:

```
## Audit Config
- src_dirs:           src,app,lib,api
- exclude_dirs:       node_modules,.next,dist,build
- progress_file_cap:  80   (optional override for the file read cap)
```

---

## Dashboard compatibility

`YYYYMMDD_hhmm-progress-report.md` is structured for ingestion by the project dashboard. The pipeline extracts:

- Run metadata from the header block (`**Baseline:**`, `**Tasks:**`)
- Scores and task counts from `## Group Breakdown` (primary) or `## Overall Completion` (fallback)

**Header block** (exact bold keys — do not rename):

```markdown
**Date:** YYYY-MM-DD HH:MM IST
**Mode:** FULL | INCREMENTAL ...
**Baseline:** true | false
**Tasks:** N total (X code, Y non-code)
```

**Score table columns** (exact names):
`Group`, `Current Score`, `Max Score`, `% Complete`, `Current Code Score`, `Max Code Score`, `% Code Complete`, `Current Non-Code Score`, `Max Non-Code Score`, `% Non-Code Complete`

**Tasks table columns** (exact names):
`Group`, `Total Done`, `Code Done`, `Non-Code Done`, `Total Partial`, `Code Partial`, `Non-Code Partial`, `Total Not Started`, `Code Not Started`, `Non-Code Not Started`, `Ambiguous Code`, `Ambiguous Non-Code`

**`_project` group**: when no task groups exist, the `## Group Breakdown` section is omitted and the dashboard falls back to `## Overall Completion` as a single `_project` row. When groups exist, a `_project` summary row must appear as the last row in each Group Breakdown table.

**`Baseline` field**: must appear in both the header block and `## Report Metadata` with the same value (`true` or `false`).

---

## Writing a compatible progress command

If you want to write your own `/project:progress` variant whose output will be picked up by the dashboard, your command must produce a report file in the exact structure below.

### Folder and filename

```
{repo root}/
└── progress-reports/
    └── YYYYMMDD_hhmm/                          ← must match ^[0-9]{8}_[0-9]{4}$  (IST timestamp)
        └── YYYYMMDD_hhmm-progress-report.md    ← timestamp prefix must match parent folder name
```

Both names must use the same timestamp string. Any run folder or file that doesn't match the patterns is silently ignored. Other files in the run folder are ignored by the parser but available for raw markdown rendering.

### Header block

Place at the top of the file. `Baseline` is the only parsed field; the others are for human readers.

```markdown
**Date:** YYYY-MM-DD HH:MM IST
**Mode:** FULL | INCREMENTAL ...
**Baseline:** true | false
**Tasks:** N total (X code, Y non-code)
```

If `Baseline` is absent, the ingestion pipeline assumes `true` and logs a warning.

### Score and task count tables

The pipeline tries **Group Breakdown first**, then falls back to **Overall Completion** if Group Breakdown is absent or empty.

**Group Breakdown (primary)** — one row per group. Use `_project` as the group name when there are no groups.

```markdown
## Group Breakdown

### Scores

| Group | Current Score | Max Score | % Complete | Current Code Score | Max Code Score | % Code Complete | Current Non-Code Score | Max Non-Code Score | % Non-Code Complete |
|-------|---------------|-----------|------------|--------------------|----------------|-----------------|------------------------|--------------------|---------------------|

### Tasks

| Group | Total Done | Code Done | Non-Code Done | Total Partial | Code Partial | Non-Code Partial | Total Not Started | Code Not Started | Non-Code Not Started | Ambiguous Code | Ambiguous Non-Code |
|-------|------------|-----------|---------------|---------------|--------------|------------------|-------------------|------------------|----------------------|----------------|--------------------|
```

**Overall Completion (fallback)** — used only when Group Breakdown is absent or empty. Stored as a single `_project` row.

```markdown
## Overall Completion

### Scores

| Metric                 | Value |
|------------------------|-------|
| Current Score          | ...   |
| Max Score              | ...   |
| % Complete             | ...   |
| Current Code Score     | ...   |
| Max Code Score         | ...   |
| % Code Complete        | ...   |
| Current Non-Code Score | ...   |
| Max Non-Code Score     | ...   |
| % Non-Code Complete    | ...   |

### Tasks

| Metric                     | Value |
|----------------------------|-------|
| Total Tasks Done           | ...   |
| Code Tasks Done            | ...   |
| Non-Code Tasks Done        | ...   |
| Total Tasks Partial        | ...   |
| Code Tasks Partial         | ...   |
| Non-Code Tasks Partial     | ...   |
| Total Tasks Not Started    | ...   |
| Code Tasks Not Started     | ...   |
| Non-Code Tasks Not Started | ...   |
| Ambiguous Code Tasks       | ...   |
| Ambiguous Non-Code Tasks   | ...   |
```

Column definitions:
- `Current Score` / `Current Code Score` / `Current Non-Code Score` — decimal partial-credit points earned (e.g. a weight-3 task at 50% contributes `1.5`).
- `Max Score` / `Max Code Score` / `Max Non-Code Score` — decimal maximum possible points.
- `% Complete` columns — percentage strings for human readability; **not stored** in the database.
- `Total Done` / `Code Done` / `Non-Code Done` — integer count of tasks at exactly 100%.
- `Total Partial` / `Code Partial` / `Non-Code Partial` — integer count of tasks between 1–99%.
- `Total Not Started` / `Code Not Started` / `Non-Code Not Started` — integer count of tasks at 0%.
- `Ambiguous Code` / `Ambiguous Non-Code` — integer count of tasks that could not be verified this run.

### Report Metadata block

`Baseline` here is the **canonical value** read by the ingestion pipeline. It must match the header block value.

```markdown
## Report Metadata

- Input CSV: <filename>
- Output dir: <path>
- Baseline: true | false
- ...
```

If `Baseline` is absent from this block, the pipeline assumes `true` and logs a warning.

### Field value rules

| Condition | Behaviour |
|---|---|
| Non-numeric value in a numeric field | Stored as `NULL`; warning logged |
| `% Complete` columns | Never persisted regardless of value |
| `Baseline` absent from Report Metadata | Assumed `true`; warning logged |
| `current_code_score + current_non_code_score ≠ current_score` (±0.05 tolerance) | Stored; warning logged |
| Both Group Breakdown and Overall Completion absent or empty | Run skipped; error logged |

### Minimal valid report

```markdown
**Baseline:** false

## Group Breakdown

### Scores

| Group    | Current Score | Max Score | % Complete | Current Code Score | Max Code Score | % Code Complete | Current Non-Code Score | Max Non-Code Score | % Non-Code Complete |
|----------|---------------|-----------|------------|--------------------|----------------|-----------------|------------------------|--------------------|---------------------|
| _project | 7.5           | 10        | 75.0%      | 7.5                | 10             | 75.0%           | 0.0                    | 0                  | —                   |

### Tasks

| Group    | Total Done | Code Done | Non-Code Done | Total Partial | Code Partial | Non-Code Partial | Total Not Started | Code Not Started | Non-Code Not Started | Ambiguous Code | Ambiguous Non-Code |
|----------|------------|-----------|---------------|---------------|--------------|------------------|-------------------|------------------|----------------------|----------------|--------------------|
| _project | 3          | 3         | 0             | 1             | 1            | 0                | 1                 | 1                | 0                    | 0              | 0                  |

## Report Metadata

- Baseline: false
```

---

## Token optimisation

The command runs `/compact` at two natural context boundaries:

1. After Phase 2 (incremental matching complete — CSV history no longer needed in context)
2. After Phase 5 (code evaluation complete — grep output no longer needed in context)

Token usage per phase is written to `token-usage.md` in the output folder.

To reduce token cost:
- Set `progress_file_cap` in `CLAUDE.md` `## Audit Config` to limit file reads.
- Use incremental runs (omit `--recheck`) — carried-forward tasks consume no file reads.
- Keep task descriptions specific enough to grep for — vague tasks are marked `ambiguous` without reading files, but they also contribute nothing to the score.
