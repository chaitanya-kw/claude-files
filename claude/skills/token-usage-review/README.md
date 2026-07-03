# token-usage-review

A Claude Code skill that analyses token usage from Claude Code session files, computes trends against previous runs, and optionally attributes changes to a described workflow change.

---

## Installation

Copy the skill folder into your Claude Code skills directory:

```bash
cp -r dashboard/token-usage-review_skill/ ~/.claude/skills/token-usage-review/
```

No third-party dependencies. Requires Python 3.8+.

The skill bundles `claude_token_report.py` — no separate install needed.

---

## Usage

Trigger from any folder by describing what you want:

```
review my token usage
analyse claude token consumption for this project
check if my new MCP changed my token usage
run a token usage report globally
```

Claude Code will:

1. Ask whether to run at **global** or **project** scope
2. Run `claude_token_report.py` against the appropriate sessions directory
3. Diff new sessions against previously processed reports in scope
4. Ask a single free-text question about any workflow changes
5. Output a structured markdown report to `.claude/` in the scope directory

### Scope behaviour

| Scope   | Sessions scanned                   | Reports read/written                  |
| ------- | ---------------------------------- | ------------------------------------- |
| Global  | `~/.claude/projects` (all)         | `~/.claude/token-usage-reviews/`      |
| Project | `~/.claude/projects/<encoded-cwd>` | `<cwd>/.claude/token-usage-reviews/`  |

### Workflow change prompt

When asked for workflow context, include:

- What changed (MCP, prompting strategy, tool)
- Roughly when (e.g. "started using Serper MCP about a week ago")

If either part is missing or ambiguous, the workflow attribution section is skipped and the reason is noted in the report.

### Output

A timestamped markdown file is written to the scope's `token-usage-reviews/` directory (inside `.claude/`):

```
YYYY_MM_DD_HHMM-token-usage-review.md
```

The report contains:

- **Token Usage Summary** — totals and per-session averages for all token types, plus cache efficiency ratio
- **Trends** — delta vs aggregate baseline from all previous reports in scope
- **New Sessions Breakdown** — per-project table of new sessions
- **Workflow Change Analysis** — correlation analysis between a described change and token signals (if sufficient data and a parseable date anchor are present)

---

## Token Optimisation

Run `/compact` after the script completes (end of Phase 2) — the session scan output is not needed in context for analysis.

Run `/compact` again after writing the output file if many prior reports were loaded during diffing.

Additional flags and practices that reduce token usage:

- The script is invoked with an explicit `--out` path to suppress stdout
- Raw JSON is never `cat`-ed into context — only required fields are extracted via `jq` or inline Python
- For large installations, use `jq` to slice only `session_id`, token counts, and timestamps from report JSON before loading into context

---

## Output

| File                                       | Location      | Description                       |
| ------------------------------------------ | ------------- | --------------------------------- |
| `YYYY_MM_DD_HHMM-claude-token-report.json` | `REPORTS_DIR` | Raw session data from the scanner |
| `YYYY_MM_DD_HHMM-token-usage-review.md`    | `REPORTS_DIR` | Human-readable analysis report    |

`REPORTS_DIR` is `~/.claude/token-usage-reviews/` for global scope, `<cwd>/.claude/token-usage-reviews/` for project scope. The folder is created automatically if it does not exist.

---

# claude-token-report script

A CLI tool that scans Claude Code session files (`.jsonl`) and produces a JSON usage report grouped by project and session.

## Requirements

- Python 3.8+
- No third-party dependencies — uses stdlib only.

## Usage

```sh
python3 claude_token_report.py <root_dir> [--out <output_file>]
```

### Arguments

| Argument       | Required | Description                                                               |
| -------------- | -------- | ------------------------------------------------------------------------- |
| `root_dir`     | Yes      | Root directory to scan recursively for `.jsonl` session files             |
| `--out <path>` | No       | Output file path. Defaults to a timestamped file in the current directory |

### Examples

Scan the default Claude Code sessions directory and write to the default timestamped output:

```sh
python3 claude_token_report.py ~/.claude/projects
```

Scan a specific directory and write output to a named file:

```sh
python3 claude_token_report.py ~/.claude/projects --out report.json
```

## Output

A JSON file with the following structure:

```json
{
  "meta": {
    "root": "/path/to/scanned/dir",
    "generated_at": "2025-04-09T14:30:00+05:30",
    "project_count": 3,
    "session_count": 12
  },
  "totals": {
    "input_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_creation_5m_tokens": 0,
    "cache_creation_1h_tokens": 0,
    "cache_read_input_tokens": 0,
    "output_tokens": 0,
    "turns": 0
  },
  "projects": [
    {
      "project": "my-project",
      "session_count": 4,
      "usage": { ... },
      "sessions": [
        {
          "session_id": "abc123",
          "first_turn_at": "2025-04-01T10:00:00Z",
          "last_turn_at": "2025-04-01T11:30:00Z",
          "models": ["claude-opus-4-5"],
          "usage": { ... }
        }
      ]
    }
  ]
}
```

### Token fields

| Field                         | Description                                |
| ----------------------------- | ------------------------------------------ |
| `input_tokens`                | Tokens sent in the request                 |
| `cache_creation_input_tokens` | Tokens written to cache (legacy field)     |
| `cache_creation_5m_tokens`    | Tokens written to 5-minute ephemeral cache |
| `cache_creation_1h_tokens`    | Tokens written to 1-hour ephemeral cache   |
| `cache_read_input_tokens`     | Tokens served from cache                   |
| `output_tokens`               | Tokens in the model's response             |
| `turns`                       | Number of assistant turns in the session   |

## Notes

- Sessions with no usage data (no `usage` field in any line) are silently skipped.
- All timestamps in the report are in ISO 8601 format. `generated_at` is in IST (UTC+5:30); session timestamps preserve the original timezone from the `.jsonl` files.
- The script is non-destructive — it only reads files.
