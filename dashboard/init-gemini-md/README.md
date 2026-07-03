# init-gemini-md

Audits an existing project and produces a `GEMINI.md` file scoped for multi-LLM workflows. Reads `AGENTS.md` for project context, infers test style from existing test files, and generates phase-specific behavioural rules for Gemini CLI covering test authoring (Phase 3a) and code review (Phase 5b).

---

## Installation

### Global (recommended — available in all projects)

```bash
mkdir -p ~/.gemini/commands
cp init-gemini-md.toml ~/.gemini/commands/
```

### Per-project

```bash
mkdir -p .gemini/commands
cp init-gemini-md.toml .gemini/commands/
```

Verify it is available in Gemini CLI:

```
/init-gemini-md
```

---

## Usage

Run from the project root in Gemini CLI:

```
/init-gemini-md
```

No flags required. The command reads `AGENTS.md` and auto-detects test style from existing test files.

**Prerequisite:** `AGENTS.md` must exist in the project root. If it does not, the command stops and instructs you to run `/init-claude-md` first (which produces `CLAUDE.md` and `AGENTS.md`).

### What happens on first run

1. Reads `AGENTS.md` to extract stack, architecture, `src_dirs`, `exclude_dirs`, and worktree conventions.
2. Locates the test directory via `AGENTS.md` or common patterns (`tests/`, `__tests__/`, `spec/`).
3. Reads up to 3 test files and up to 3 related source files to infer test style: naming conventions, structure (BDD/AAA/table-driven), assertion patterns, and import style.
4. If no test files exist, skips inference and notes it explicitly — the generated file falls back to industry-standard conventions for the detected stack.
5. Writes `GEMINI.md` to the project root.

### What happens if GEMINI.md already exists

The command overwrites the file. No diff review step is offered — re-run is always a full regeneration from current `AGENTS.md` and test file state.

### HANDOFF.md and OVERRIDE.md

Two runtime files are referenced by the generated `GEMINI.md` but are never created by this command:

- **`HANDOFF.md`** — written by Gemini at the worktree root if it hits a token limit mid-task. Documents what was completed, what is in progress, and what remains.
- **`OVERRIDE.md`** — placed manually in the project root to authorise temporary exceptions to worktree scope rules. Gemini reads it before starting any task if present.

Add both to `.gitignore`:

```
HANDOFF.md
OVERRIDE.md
```

---

## Output

A `GEMINI.md` file written to the project root with these sections:

| Section                        | Contents                                                                                  |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| `## Purpose`                   | One-sentence scope statement; references `AGENTS.md` as required reading                  |
| `## Worktree scope`            | Phase ownership (`tests/*` for 3a, no worktree for 5b) and `OVERRIDE.md` protocol         |
| `## Token limit protocol`      | Steps Gemini must follow when hitting a token limit mid-task                              |
| `## Phase 3a — Test authoring` | What to read, inferred style rules, hard constraints (no implementation, must-fail tests) |
| `## Phase 5b — Review pass`    | What to read, output format, review scope, no-modification constraint                     |
| `## Hard rules (all phases)`   | Scope, dependency, env, and contract deviation rules applied to every phase               |

The total file reads across all phases is capped at 10.
