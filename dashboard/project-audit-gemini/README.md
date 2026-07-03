# gemini-audit

Gemini-scoped pass for an existing project audit. Analyses test coverage and comment/doc compliance, produces `D-test-docs.md`, and updates the `AUDIT-SUMMARY.md` written by `/project:audit`. Must be run after the Claude pass.

---

## Installation

### Global (recommended — available in all projects)

```bash
mkdir -p ~/.gemini/commands
cp gemini-audit.md ~/.gemini/commands/gemini-audit.md
```

### Per-project

```bash
mkdir -p .gemini/commands
cp gemini-audit.md .gemini/commands/gemini-audit.md
```

---

## Usage

```
/gemini-audit
```

Run from the repo root after `/project:audit` has completed. The command auto-locates the most recent `audit-reports/YYYYMMDD_hhmm/` subfolder and operates on it.

No flags are required.

---

## Prerequisites

- `/project:audit` must have been run first. The command expects an existing `AUDIT-SUMMARY.md` in the most recent audit subfolder.
- `CLAUDE.md` or `AGENTS.md` must be present in the repo root for stack and config resolution.
- The detected test runner must be installed and accessible on `PATH`.

---

## Output

All output is written into the existing audit subfolder located during recovery.

| File               | Contents                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `D-test-docs.md`   | Test coverage analysis and comment/doc compliance findings, metrics, and recommendations                           |
| `AUDIT-SUMMARY.md` | Updated in place — Test Coverage and Comment/Doc Compliance rows, Baseline Metrics table, and Gemini Pass appendix |

### What is updated in AUDIT-SUMMARY.md

The command makes targeted, in-place edits only. Sections not listed here are never modified.

| Target                                         | Change                                                               |
| ---------------------------------------------- | -------------------------------------------------------------------- |
| Findings Overview — Test Coverage row          | Replaces placeholder counts with actual severity counts              |
| Findings Overview — Comment/Doc Compliance row | Replaces placeholder counts with actual severity counts              |
| Baseline Metrics — Test coverage %             | Replaces `pending` with actual value                                 |
| Baseline Metrics — Comment/Doc compliance %    | Replaces `pending` with actual value                                 |
| Baseline Metrics — Test file count             | Replaces `pending` with actual value                                 |
| End of file                                    | Appends `## Gemini Pass` block with model, file count, and timestamp |

---

## Token Optimisation

This command spawns a single subagent for all grep scans and test runner execution. The orchestrator context stays lean — only config, recovery, and final file writes happen in the main context.

To reduce token cost:

- Keep `src_dirs` tight in `CLAUDE.md` `## Audit Config`. The subagent scans only the declared source directories.
- Set `exclude_dirs` to cover build output and generated files — these inflate grep hit counts without adding signal.
- If test coverage output is verbose (pytest with full term-missing output), the subagent reads only the tail (last 35 lines). No truncation config is needed.
- The spot-check cap for doc compliance is hardcoded at 20 source files. There is no flag to raise this — if compliance coverage is insufficient, tighten `src_dirs` to scope the scan more precisely.
