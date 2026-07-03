# init-claude-md

Audits an existing project and produces project context files. In single-LLM projects,
produces a high-signal `CLAUDE.md`. In multi-LLM projects (Claude Code + Gemini CLI),
produces `AGENTS.md` (shared ground truth) and a slim `CLAUDE.md` (Claude-specific only),
then prints the brief needed to generate `GEMINI.md` via a Gemini CLI custom command.

Covers stack, dev commands, architecture, business logic, inconsistencies, conventions,
out-of-scope boundaries, and audit config for `/project:audit`. Token-efficient: uses
Glob and Grep before reading files.

---

## Installation

### Personal (available in all projects)

```bash
mkdir -p ~/.claude/skills/init-claude-md
cp SKILL.md ~/.claude/skills/init-claude-md/
```

### Project-local

```bash
mkdir -p .claude/skills/init-claude-md
cp SKILL.md .claude/skills/init-claude-md/
```

Verify it is available in Claude Code:

```
/init-claude-md
```

---

## Usage

Run from the project root in Claude Code:

```
/init-claude-md
```

No flags required. The command asks two questions before auditing:

1. **Is this a multi-LLM project?** (yes / no) — determines which files are produced
2. **TDD default?** (yes / no / ask per task) — single-LLM only; always on in multi-LLM

### Telemetry check (Phase 0c)

Before auditing, the command checks whether the per-project telemetry config is in place:

| File                    | Platform      | What is checked                                                             |
| ----------------------- | ------------- | --------------------------------------------------------------------------- |
| `.envrc`                | Linux / macOS | Contains `export OTEL_RESOURCE_ATTRIBUTES=…`                                |
| `.vscode/settings.json` | Windows       | Contains `OTEL_RESOURCE_ATTRIBUTES` under `terminal.integrated.env.windows` |

If both files are present and contain the expected export, nothing is printed and the audit continues.
If either is missing or the key is absent, a warning is printed listing what is missing. The audit is **not blocked** — the warning is informational only.

Refer to the **Claude Code Telemetry Setup** guide for the per-project setup steps.

### What happens on first run

1. Probes the project structure using Glob (no file reads yet).
2. Reads package manifests, config files, env examples, and entry points within a token budget.
3. Samples business logic using Grep-first targeted reads.
4. Asks two optional questions: SRS/PRD/brief to factor in; related repos or services.
5. Detects inconsistencies between declared and actual dependencies, env vars, scripts.
6. Resolves all Audit Config values (used by `/project:audit`).
7. Writes output files.

### What happens on re-run (files already exist)

The command detects existing files and asks:

> "I found [CLAUDE.md / AGENTS.md / both]. Do you want to (1) full rewrite, or (2) review a diff before overwriting?"

- **Full rewrite**: completes all phases, overwrites, summarises what changed.
- **Diff review**: completes all phases, displays proposed content, waits for confirmation.

---

## Token Optimisation

Run `/compact` at these two points:

- After **Phase 3** on Large projects (post-subagent synthesis).
- After **Phase 7** drafting, before writing files.

Additional flags and config that reduce token usage:

- `disable-model-invocation: true` is set in the skill frontmatter — do not remove it. It prevents nested model calls.
- Grep before Read is enforced in every phase. A file not Grepped is a file not read.
- Keep output files within their line budgets (`CLAUDE.md` ≤ 150 lines excluding Audit Config; multi-LLM `CLAUDE.md` ≤ 40 lines) to reduce context on re-runs.

---

## Output

### Single-LLM

`CLAUDE.md` — written to the project root.

### Multi-LLM

`AGENTS.md` — shared ground truth for all agents, written to the project root.
`CLAUDE.md` — Claude-specific constraints only (≤ 40 lines), written to the project root.

After writing, the command prints a brief you can paste directly into Gemini CLI to generate `GEMINI.md` via the `init-gemini-md` custom command.
