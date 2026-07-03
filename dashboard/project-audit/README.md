# project-audit

Full baseline audit of the current branch. In single-LLM projects, covers all
domains. In multi-LLM projects (detected via `AGENTS.md`), covers only
Claude-scoped domains: dependency vulnerabilities, semgrep static analysis,
security (OWASP), error handling, logical errors, tech debt, and type safety.

Test coverage and comment/doc compliance are handled by a separate Gemini CLI
audit command in multi-LLM projects.

---

## Installation

### Personal (available in all projects)

```bash
mkdir -p ~/.claude/skills/project-audit
cp SKILL.md ~/.claude/skills/project-audit/
```

### Project-local

```bash
mkdir -p .claude/skills/project-audit
cp SKILL.md .claude/skills/project-audit/
```

Verify it is available in Claude Code:

```
/project-audit
```

### Required dependencies

The command will attempt to auto-install `semgrep` and `pip-audit` on first run.
You will need:

- `git` — must be installed manually
- `node` / `npm` — for Node.js projects
- `python3` — for Python projects
- `dotnet` CLI — for .NET projects
- `claude-security-audit` — must be installed separately:

```bash
git clone https://github.com/afiqiqmal/claude-security-audit /tmp/cc-sec-audit
mkdir -p ~/.claude/commands
cp /tmp/cc-sec-audit/.claude/commands/security-audit.md ~/.claude/commands/
cp -r /tmp/cc-sec-audit/references ~/.claude/security-audit-references
```

---

## Usage

```
/project:audit
/project:audit --full
```

- (no flag) — runs a lite OWASP security scan
- `--full` — runs the complete OWASP scan (slower)

Run from the root of the project you want to audit. The branch to audit must be
checked out before running.

### Mode detection

The command detects project mode automatically by checking for `AGENTS.md`:

| Condition           | Mode       | Behaviour                                                   |
| ------------------- | ---------- | ----------------------------------------------------------- |
| `AGENTS.md` present | Multi-LLM  | Runs subagents A, B, C only. Prompts to run Gemini command. |
| `AGENTS.md` absent  | Single-LLM | Runs all subagents A, B, C, D. Full report.                 |

Config is read from `AGENTS.md` (multi-LLM) or `CLAUDE.md` (single-LLM) via
the `## Audit Config` block.

---

## Two-pass audit (multi-LLM projects)

In multi-LLM projects the audit runs in two sequential passes.

**Pass 1 — Claude Code (`/project:audit`)**

Runs Claude-scoped subagents (A, B, C) and the OWASP security scan. Produces
`AUDIT-SUMMARY.md` with Test Coverage and Comment/Doc Compliance rows marked
to indicate the Gemini pass is required. At completion, prints:

```
Claude pass complete. Run the Gemini audit command to finish the audit:
  /project:audit-gemini
```

**Pass 2 — Gemini CLI (`/project:audit-gemini`)**

A separate Gemini CLI custom command. Locates the most recent Claude pass output,
runs test coverage and doc compliance analysis, and updates `AUDIT-SUMMARY.md`
in place.

To create the Gemini CLI custom command, use the `project-audit-gemini` brief
in `docs/draft-multi-llm-workflow.md`.

The dashboard ingests one `AUDIT-SUMMARY.md` per run folder. It is complete only
after both passes have run.

---

## Output

All output is written to a timestamped subfolder: `audit-reports/YYYYMMDD_hhmm/`

| File                | Contents                                                                                      |
| ------------------- | --------------------------------------------------------------------------------------------- |
| `AUDIT-SUMMARY.md`  | Primary report — findings overview, top action items, baseline metrics                        |
| `A-deps-secrets.md` | Dependency CVEs and suspected hardcoded secrets                                               |
| `B-error-logic.md`  | Error handling issues and structural logical errors                                           |
| `C-tech-debt.md`    | Tech debt markers, debug leaks, type safety bypasses, lint summary                            |
| `D-test-docs.md`    | Test coverage and comment/doc compliance — Gemini pass (multi-LLM) or subagent D (single-LLM) |
| `security-audit.md` | OWASP security audit report                                                                   |
| `token-usage.md`    | Per-step token consumption and compaction savings                                             |
| `00-config.txt`     | Resolved audit configuration                                                                  |
| `deps-vuln.json`    | Raw dependency vulnerability scan output                                                      |
| `semgrep.json`      | Raw semgrep static analysis output                                                            |
| `lint.txt`          | Raw linter output                                                                             |
| `coverage.txt`      | Raw test coverage output — single-LLM only                                                    |
| `pattern-*.txt`     | Raw grep pattern scan outputs                                                                 |
| `metrics-*.txt`     | Codebase size metrics                                                                         |

---

## AGENTS.md / CLAUDE.md integration

The command reads `## Audit Config` from `AGENTS.md` if present, otherwise from
`CLAUDE.md`. Run `/init-claude-md` first to generate the appropriate file with
the correct config block.

Recognised keys:

```
## Audit Config
- package_manager:  npm | yarn | pnpm | pip | dotnet | cargo
- test_runner:      jest | vitest | pytest | dotnet-test
- lint_cmd:         <full shell command>
- src_dirs:         src,app,lib,api   (comma-separated, relative to repo root)
- exclude_dirs:     node_modules,.next,dist,build,bin,obj
- docstring_style:  jsdoc | google | numpy | sphinx
```

---

## Dashboard compatibility

`AUDIT-SUMMARY.md` is structured for ingestion by the project dashboard. In
multi-LLM projects, ingest only after both passes have completed.

**Canonical domain labels:**

| Domain label             | Populated by                                       |
| ------------------------ | -------------------------------------------------- |
| `Security (OWASP)`       | Claude pass                                        |
| `Dependencies (CVE)`     | Claude pass                                        |
| `Error Handling`         | Claude pass                                        |
| `Logical Errors`         | Claude pass                                        |
| `Tech Debt`              | Claude pass                                        |
| `Type Safety (TS)`       | Claude pass                                        |
| `Test Coverage`          | Gemini pass (multi-LLM) / Claude pass (single-LLM) |
| `Comment/Doc Compliance` | Gemini pass (multi-LLM) / Claude pass (single-LLM) |

Use `—` (em dash) for severity columns that do not apply to a domain.

**Header block** (exact bold keys — do not rename):

```markdown
**Date:** YYYY-MM-DD HH:MM IST
**Mode:** FULL | CLAUDE PASS — Gemini pass required
**Baseline:** true | false
```

---

## Token optimisation

The command runs `/compact` at four natural context boundaries:

1. After Step 1 (pre-flight complete)
2. After Step 2 (config resolved)
3. After Step 4 (security audit complete)
4. After Step 5 (all subagents complete)

Token usage per step is written to `token-usage.md`.

To reduce token cost:

- Set `src_dirs` and `exclude_dirs` tightly in the Audit Config block.
- In multi-LLM mode, test coverage and doc compliance grep scans are skipped
  entirely in the Claude pass — these run only in the Gemini pass.
