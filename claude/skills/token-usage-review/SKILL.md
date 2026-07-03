---
name: token-usage-review
description: Analyses Claude Code token usage from session files and produces a structured report with trends and cache efficiency metrics. Use when the user asks to review token usage, check Claude token consumption, analyse session costs, run a token usage report, or evaluate the effect of a workflow change on token usage.
when_to_use: Trigger when the user mentions token usage, token costs, session analysis, cache efficiency, cache hit rate, or wants to understand how their Claude Code usage has changed over time. Also trigger when the user describes a recent workflow change (new MCP, prompting strategy, tool) and wants to know whether it affected their token consumption.
argument-hint: "[global|project]"
allowed-tools: Bash(python3 *) Bash(find *) Bash(mkdir *) Bash(jq *)
---

# Token Usage Review Skill

Produce a structured token usage report from Claude Code session files, with trend analysis and optional workflow change attribution.

## Quick Start

1. Ask the user: global or project scope
2. Run `claude_token_report.py` to generate a new JSON report
3. Load all previous reports in scope to build the processed session set
4. Elicit workflow context
5. Analyse and summarise
6. Write output `.md` to `.claude/` in the appropriate scope directory

---

## Phase 1 — Determine Scope

Ask the user before doing anything else:

> "Run this at the **global** level (all projects, `~/.claude/`) or **project** level (current directory only)?"

Set variables based on answer:

| Variable        | Global                                | Project                                          |
| --------------- | ------------------------------------- | ------------------------------------------------ |
| `SESSIONS_ROOT` | `~/.claude/projects`                  | `~/.claude/projects/<encoded-cwd>`               |
| `REPORTS_DIR`   | `~/.claude/token-usage-reviews/`      | `<cwd>/.claude/token-usage-reviews/`             |
| `SCOPE_LABEL`   | `global`                              | `project`                                        |

For project scope, the encoded project path uses Claude Code's convention: replace `/` with `-` in the absolute path, strip leading `-`. If the encoded directory does not exist under `~/.claude/projects/`, inform the user that no sessions were found for this project and stop.

Ensure `REPORTS_DIR` exists:

```bash
mkdir -p "$REPORTS_DIR"
```

---

## Phase 2 — Run the Report Script

Locate the bundled script relative to this skill file:

```bash
SCRIPT_DIR="$(dirname "$0")"
SCRIPT="$SCRIPT_DIR/claude_token_report.py"
```

Generate a timestamped output file in `REPORTS_DIR`:

```bash
TS=$(date +"%Y_%m_%d_%H%M" --utc)  # adjust to IST: TZ=Asia/Kolkata date +"%Y_%m_%d_%H%M"
OUT="$REPORTS_DIR/${TS}-claude-token-report.json"

python3 "$SCRIPT" "$SESSIONS_ROOT" --out "$OUT"
```

If the script fails (non-zero exit), report the error and stop. Do not proceed with an incomplete report.

---

## Phase 3 — Load Previous Reports and Diff

Find all prior reports in `REPORTS_DIR` (exclude the one just generated):

```bash
find "$REPORTS_DIR" -name "*-claude-token-report.json" ! -name "$(basename $OUT)" | sort
```

From each prior report, collect all `session_id` values across all projects. Build the set `PROCESSED_SESSION_IDS`.

From the new report, identify:

- `NEW_SESSIONS`: sessions whose `session_id` is not in `PROCESSED_SESSION_IDS`
- `CARRIED_SESSIONS`: all others (already seen — for trend baseline only)

If there are no prior reports, all sessions are treated as new and trend deltas are not computed.

---

## Phase 4 — Elicit Workflow Context

Ask the user **one question**:

> "Have you made any workflow changes since your last review that you'd like factored into the analysis? For example: a new MCP, a different prompting strategy, a new tool. Include roughly when the change happened (e.g. 'started using Context7 about a week ago'). Type **none** to skip."

Store the full response as `WORKFLOW_CONTEXT`.

Parse `WORKFLOW_CONTEXT` for:

1. A date/time anchor — look for relative expressions ("last week", "3 days ago", "since Monday") or absolute dates. Convert to an ISO date using today's date as reference.
2. A change description — the nature of the change (MCP, prompting, tool, other).

If either cannot be extracted, set `WORKFLOW_ANALYSIS_ENABLED = false` and note the reason. Do not attempt partial analysis.

---

## Phase 5 — Analyse

### 5a. Token type summary

For the **new sessions only**, compute per-session averages and totals for each token field:

| Field                         | Label                |
| ----------------------------- | -------------------- |
| `input_tokens`                | Input                |
| `cache_creation_5m_tokens`    | Cache Write (5m)     |
| `cache_creation_1h_tokens`    | Cache Write (1h)     |
| `cache_creation_input_tokens` | Cache Write (legacy) |
| `cache_read_input_tokens`     | Cache Read           |
| `output_tokens`               | Output               |

Compute **cache efficiency ratio**:

```
cache_efficiency = cache_read_input_tokens / (cache_creation_5m_tokens + cache_creation_1h_tokens + cache_creation_input_tokens + input_tokens)
```

Express as a percentage. Higher = better cache utilisation.

### 5b. Trend comparison

If prior reports exist, compare new session averages against the aggregate baseline (all CARRIED_SESSIONS across all prior reports). For each token type, compute:

- Absolute delta (new avg − baseline avg)
- Percentage delta

Flag notable changes (>20% delta) explicitly.

### 5c. Workflow change attribution (if `WORKFLOW_ANALYSIS_ENABLED = true`)

Split sessions by the parsed date anchor into `PRE` and `POST` cohorts.

**Minimum cohort guard**: If either cohort has fewer than 3 sessions, skip this section and note: "Insufficient sessions in one cohort (minimum 3 required) — workflow attribution skipped."

For each token type and the cache efficiency ratio, compute PRE vs POST averages and deltas.

Frame all findings as **correlations**, not causes. Use language like:

- "Sessions after the reported change show..."
- "This is consistent with..."
- Never use "caused", "because of", or "due to".

Map change type to expected signals:

- **MCP added**: expect higher cache creation + cache read per turn
- **Prompting strategy change**: expect change in input tokens per turn; may affect output tokens
- **New tool usage**: similar to MCP — watch cache creation and turns per session

If the described change does not map to any measurable signal, note that and skip the section.

---

## Phase 6 — Write Output

Compose the report as a markdown file. Save to:

```
$REPORTS_DIR/YYYY_MM_DD_HHMM-token-usage-review.md
```

(IST timestamp, same convention as other outputs.)

### Report structure

```markdown
# Token Usage Review — [SCOPE_LABEL] — [DATE]

## Scope

- Level: [global | project]
- Sessions analysed (new): N
- Sessions in baseline: N
- Reports found: N previous

## Token Usage Summary

| Token Type           | Total (new) | Avg / Session | Δ vs Baseline |
| -------------------- | ----------- | ------------- | ------------- |
| Input                | ...         | ...           | ...           |
| Cache Write (5m)     | ...         | ...           | ...           |
| Cache Write (1h)     | ...         | ...           | ...           |
| Cache Write (legacy) | ...         | ...           | ...           |
| Cache Read           | ...         | ...           | ...           |
| Output               | ...         | ...           | ...           |

**Cache efficiency ratio:** X% [▲/▼ vs baseline]

## Trends

[Narrative of notable changes. If no baseline, state this explicitly.]

## New Sessions Breakdown

[Per-project table: project name | new sessions | input avg | output avg | cache efficiency]

## Workflow Change Analysis

[Either the attribution analysis, or the reason it was skipped.]
```

After writing the file, print the path to the user and display the report inline in chat.

---

## Token Optimisation

Run `/compact` after Phase 2 (after the script has run and the JSON is on disk) — the raw session scan output is not needed in context for the analysis phases.

Also run `/compact` after Phase 6 if the session involved many prior reports being loaded for diffing.

Flags that reduce token usage:

- Pass `--out` explicitly to `claude_token_report.py` to avoid any stdout pollution
- Do not `cat` the full JSON report into context — parse only the fields needed (session IDs, token counts, timestamps) using `python3 -c` or `jq` inline commands
- For large installations (many projects/sessions), use `jq` to extract only required fields rather than loading the full JSON

---

## Error Handling

| Condition                      | Action                                                                                       |
| ------------------------------ | -------------------------------------------------------------------------------------------- |
| `SESSIONS_ROOT` does not exist | Inform user, stop                                                                            |
| Script exits non-zero          | Show stderr, stop                                                                            |
| No sessions with usage data    | Inform user, stop                                                                            |
| New report has 0 new sessions  | Inform user that all sessions were already processed; offer to re-run ignoring prior reports |
| Workflow context unparseable   | Set `WORKFLOW_ANALYSIS_ENABLED = false`, note reason in report                               |
| Either cohort < 3 sessions     | Skip attribution section, note in report                                                     |
