# task-to-progress-csv

Converts a task list into the CSV input format required by the `/project:progress`
command. Handles multiple input formats, infers task type and status, assigns stable
IDs for incremental matching, gates file creation behind a preview table, and
validates output before presenting it for download.

---

## Installation

This is a Claude web interface skill, not a Claude Code command.

### Add to the Claude web interface

1. Go to **Claude.ai → Settings → Custom skills** (or the equivalent in your
   organisation's Claude deployment).
2. Upload or paste the contents of `SKILL.md`.
3. The skill activates automatically when you mention `/project:progress` or the
   "progress review command" in the context of preparing a task list CSV.

> The skill will not trigger for general task lists or to-do requests unrelated
> to `/project:progress`. Mention the command explicitly to activate it.

---

## Usage

Paste or upload your task list in any of these formats:

- Plain text (bullets, numbered lists, free prose)
- Markdown task lists (`- [ ] task` or `- [x] done task`)
- A pasted table or spreadsheet content
- An uploaded `.txt`, `.md`, or `.csv` file

Then mention `/project:progress` or ask to prepare the CSV for the progress review
command. Examples:

> "Convert this task list to a CSV for /project:progress"

> "Prepare a progress CSV from these tasks"

> "I need to run /project:progress — here's my task list: ..."

---

## What the skill does

1. Parses the input into a flat list of tasks, stripping list markers, numbering,
   and checkbox syntax.
2. Infers `type` (`code` or `non-code`) and `status` (for non-code tasks) from
   task descriptions where not explicitly provided.
3. Infers `group` from section headers or labels in the input.
4. Assigns stable `id` slugs (e.g. `auth-1`, `pay-2`) for incremental matching
   across `/project:progress` runs.
5. Asks at most one clarifying question if the input is ambiguous in a way that
   affects many rows.
6. **Presents a Markdown table preview for your approval before creating any file.**
   You can request edits at this stage — the skill re-presents the table until you
   approve.
7. On approval, generates a fully validated CSV and presents it for download.

---

## Output CSV format

The output file is named `YYYY_MM_DD_HHMM-tasks.csv` (IST). It contains 13 columns
in this exact order:

| Column | Populated by | Notes |
|---|---|---|
| `id` | skill | Stable slug: `<group>-<n>` or `task-<n>` |
| `task` | skill | Cleaned description |
| `type` | skill | `code` or `non-code` |
| `status` | skill | Non-code: inferred or `not-started`. Code: blank unless stated. |
| `weight` | `/project:progress` | Blank unless you explicitly provide a value |
| `group` | skill | From section headers or labels; blank if none |
| `notes` | skill | Sub-bullets or parentheticals from input; blank if none |
| `confidence` | `/project:progress` | Always blank |
| `done_pct` | `/project:progress` | Always blank |
| `ambiguity_reason` | `/project:progress` | Always blank |
| `weight_rationale` | `/project:progress` | Always blank |
| `grep_hits` | `/project:progress` | Always blank |
| `source` | `/project:progress` | Always blank |

Columns owned by `/project:progress` are never populated by this skill — they are
filled in during command execution.

### Where to place the output

For a first run of `/project:progress`:

```bash
cp YYYY_MM_DD_HHMM-tasks.csv <project-root>/progress-reports/initial-tasks.csv
```

`initial-tasks.csv` is the permanent scope baseline. It is never overwritten by
`/project:progress`.

For subsequent runs, you can pass the CSV directly:

```
/project:progress path/to/YYYY_MM_DD_HHMM-tasks.csv
```

---

## Inference rules (quick reference)

**type**

- `code`: building, implementing, fixing, refactoring, integrating, migrating,
  deploying, or any named technical artifact (API, component, schema, service, test).
- `non-code`: documentation, design, review, approval, meeting, sign-off, legal,
  compliance, procurement. When ambiguous, defaults to `code`.

**status (non-code tasks only)**

| Signal | Assigned status |
|---|---|
| "done", "complete", "finished", "✓", `[x]` | `done` |
| "in progress", "WIP", "ongoing", "started" | `in-progress` |
| "blocked", "waiting", "on hold", "pending" | `blocked` |
| No signal | `not-started` (mandatory default) |

---

## Constraints

- No file is created until you explicitly approve the preview table.
- The skill never invents tasks not present in the input.
- Explicit values in your input always take precedence over inferred values.
- `weight` is left blank unless you explicitly provide a value for a specific task.
- Output is always valid CSV with all fields double-quoted (`csv.QUOTE_ALL`).
