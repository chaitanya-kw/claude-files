---
name: init-claude-md
description: Audit an existing project and produce CLAUDE.md (single-LLM projects) or AGENTS.md + CLAUDE.md (multi-LLM projects). Covers stack, dev commands, architecture, business logic, inconsistencies, conventions, out-of-scope boundaries, and audit config for /project:audit. Token-efficient: uses Glob and Grep before reading files.
allowed-tools: Read, Write, Glob, Grep, Bash
disable-model-invocation: true
---

## Purpose

You are producing project context files for an existing project. Your goal is output that is **accurate, terse, and high-signal**. Every line must earn its place. Do not add boilerplate, aspirational statements, or anything that can be inferred trivially from the stack.

---

## Phase 0 — Pre-flight and mode selection

### 0a. Check for existing files

Check whether `CLAUDE.md` or `AGENTS.md` already exist in the project root.

- If neither exists: proceed to Phase 0b.
- If either exists: read the existing file(s), then ask the user:

  > "I found [CLAUDE.md / AGENTS.md / both]. Do you want to (1) full rewrite, or (2) review a diff before overwriting?"

  Store their choice. Proceed to Phase 0b and complete all phases before writing anything.

### 0b. Mode selection

Ask the user two questions together:

> "Before I audit the project, two quick questions:
>
> 1. Is this a multi-LLM project — will Claude Code and Gemini CLI both work on this codebase? (yes / no)
> 2. [Single-LLM only] Do you want TDD as the default development approach? (yes / no / ask per task)"

Question 2 is only asked if the answer to question 1 is no. In multi-LLM projects TDD is always on — the Red/Green worktree split requires it.

Store:

- `IS_MULTI_LLM` = true | false
- `TDD_MODE` = on | off | per-task (single-LLM only; always `on` if multi-LLM)

### 0c. Telemetry check

Check whether the telemetry configuration files are present in the project root.

**Linux / macOS — check for `.envrc`:**

Use `Bash` to test:

```bash
grep -s "OTEL_RESOURCE_ATTRIBUTES" .envrc
```

**Windows (VSCode) — check for `.vscode/settings.json`:**

Use `Bash` to test:

```bash
grep -s "OTEL_RESOURCE_ATTRIBUTES" .vscode/settings.json
```

**Evaluation rules:**

- If **both files exist and contain the `OTEL_RESOURCE_ATTRIBUTES` export**: do nothing. Proceed to Phase 1 silently.
- If **either file is missing or does not contain the `OTEL_RESOURCE_ATTRIBUTES` export**: print the following message and continue to Phase 1.

```
⚠ Telemetry config incomplete for this project.

Missing or incomplete:
  [list whichever apply]
  - .envrc  (Linux/macOS — must export OTEL_RESOURCE_ATTRIBUTES)
  - .vscode/settings.json  (Windows — must set terminal.integrated.env.windows.OTEL_RESOURCE_ATTRIBUTES)

Ask your team lead for the Claude Code Telemetry Setup guide and follow the
per-project setup step before your first Claude Code session in this repo.
```

Do not block or halt. This is informational only.

---

## Phase 1 — Structure probe (Glob only, no file reads)

Use `Glob` to map the project. Do not read file contents yet.

Determine:

- Top-level directory layout
- Presence and location of: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `composer.json`, `.csproj`/`.sln`, or equivalent
- Presence of: `docker-compose.*`, `Dockerfile`, `.env.example`, `.env.sample`, `*.config.*`, `turbo.json`, `nx.json`
- Presence of: `docs/`, `specs/`, `architecture/`, `ADR/`, `decisions/` directories
- Presence of existing `README.md`, `CHANGELOG.md`
- Test directories: `__tests__/`, `tests/`, `spec/`, `cypress/`, `e2e/`
- CI config: `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`
- Linter config: `.eslintrc.*`, `eslint.config.*`, `ruff.toml`, `.pylintrc`, `.rubocop.yml`
- Planning docs: `SCOPE.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `API_CONTRACTS.md`, `DESIGN_BRIEF.md`, `IMPLEMENTATION_PLAN.md`, `CONTRACTS.ts`, `CONTRACTS.py`

**Project size classification:**

| Signal                                                                   | Classification | Phase 2 read cap |
| ------------------------------------------------------------------------ | -------------- | ---------------- |
| <5 top-level source dirs, single package manifest                        | Small          | 8 files          |
| 5–15 source dirs, or 2–4 package manifests                               | Medium         | 15 files         |
| >15 source dirs, monorepo markers (turbo/nx/workspaces), or >4 manifests | Large          | 25 files         |

Record the classification and cap before proceeding.

---

## Phase 2 — Targeted reads (respect the cap from Phase 1)

Read files in this priority order, stopping when you hit the cap:

1. All package manifests (`package.json`, `pyproject.toml`, etc.)
2. `.env.example` or `.env.sample`
3. Primary config files (`next.config.*`, `vite.config.*`, `tsconfig.json`, `tailwind.config.*`, `app.config.*`, etc.)
4. `README.md`
5. Existing `CLAUDE.md` or `AGENTS.md` (if not already read in Phase 0a)
6. Root-level entry points (`main.*`, `index.*`, `app.*`, `server.*`, `Program.cs`, etc.)

Do not read source files speculatively.

---

## Phase 3 — Business logic sampling

Use `Grep` and `Glob` to locate high-signal source files. Then read selectively.

**Step 1 — Locate domain terms.** Grep for:

- Route/endpoint definitions: `router.`, `app.get`, `app.post`, `@Get`, `@Post`, `MapGet`, `MapPost`, `createRoute`, `path=`
- Model/schema definitions: `schema`, `model`, `entity`, `interface`, `type.*=`, `class.*{`
- Service layer: files named `*.service.*`, `*.repository.*`, `*.usecase.*`, `*.handler.*`
- Auth/permission patterns: `middleware`, `guard`, `permission`, `role`, `policy`
- Business rule constants or enums: `enum`, `const.*=.*{`, `RULES`, `LIMITS`, `CONFIG`

**Step 2 — Read selectively.** From Grep results, read only:

- Up to 3 route/controller files (prefer the most populated ones)
- Up to 3 model/schema files
- Up to 2 service files
- Auth middleware (1 file)

**On monorepos (Large classification) with 3+ distinct packages:** spawn a subagent per package for this phase. Each subagent runs Steps 1–2 scoped to its package directory and returns a summary.

**Step 3 — Docs scan.** If `docs/`, `specs/`, or similar directories exist:

- Glob for `*.md` files within them
- Read any file whose name suggests: SRS, PRD, ADR, architecture, overview, domain, glossary
- Cap: 5 files total

**Step 4 — User context.**

> "Do you have an SRS, PRD, or brief you want me to factor into the business logic section? Paste it here, or press Enter to skip."

**Step 5 — Related systems discovery.**

Scan for interface boundary signals (OpenAPI/GraphQL/proto files, shared type packages, external service env vars, generated client directories). Then ask:

> "Does this project integrate with a separate repo or service? If yes, what is it?"

Follow up based on signals found. Extract only: system name, auth mechanism, data contract, constraints.

---

## Phase 4 — Inconsistency detection

Cross-reference what has been found. Flag only real discrepancies:

- Deps vs imports: unused dependencies or imports referencing unlisted packages
- Env vars: referenced in code but absent from `.env.example`
- Scripts vs reality: scripts referencing files or tools that don't exist on disk
- Stack claims vs actuality: context files claiming technology not present in manifests
- Dead config: config files for tools with no corresponding dependency

Record each as: `[file or area] — [what was claimed/expected] vs [what was found]`

---

## Phase 5 — Audit Config resolution

Resolve values without reading new files.

| Key               | Derive from                                                                                                                   |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `package_manager` | Presence of `yarn.lock`, `pnpm-lock.yaml`, `package-lock.json`, or `Pipfile.lock`                                             |
| `test_runner`     | `scripts` in `package.json`, presence of `jest.config.*`, `vitest.config.*`, `pytest.ini`, `pyproject.toml [tool.pytest]`     |
| `lint_cmd`        | Linter config + scripts. Default to `npx eslint . --format compact` for Node, `ruff check .` for Python if no script defined. |
| `src_dirs`        | Top-level source directories from Phase 1. Comma-separated, relative to repo root.                                            |
| `exclude_dirs`    | Build output, dependency caches, generated code.                                                                              |
| `docstring_style` | Infer from existing docstrings in sampled source files.                                                                       |

---

## Phase 6 — Planning docs inventory

If any of the planning doc files from Phase 1 exist, record them in a table:

| File | Purpose (one line) |
| ---- | ------------------ |
| …    | …                  |

Omit this phase entirely if no planning docs were found.

---

## Phase 7 — Draft output

### Single-LLM: produce CLAUDE.md

```markdown
# CLAUDE.md

## Project

[One paragraph. What this project does, who it is for, and the primary domain.]

## Stack

[Terse list. Format: `technology — version constraint` only where version matters.]

## Dev commands

[install, dev/start, build, test, lint, migrate — only commands actually used]

## Architecture

[Key directories and what lives in them. 1 line per directory.]
[Non-obvious patterns: e.g. "all business logic in services/, controllers are thin"]

## Business logic

[Domain entities and the rules that govern them.]
[Format: entity or concept → rule or constraint.]

## Related systems

[Only if a related system was identified. Omit entirely otherwise.]

## Development approach

[Conditional — see TDD_MODE rules above]

## Conventions

[Patterns Claude must follow. Only what is actually enforced in the codebase.]

## Known inconsistencies

[Output from Phase 4. Omit section entirely if none found.]

## Out of scope

[Areas Claude should not touch without explicit instruction.]

## Audit Config

- package_manager: <resolved>
- test_runner: <resolved>
- lint_cmd: <resolved>
- src_dirs: <resolved>
- exclude_dirs: <resolved>
- docstring_style: <resolved>
```

---

### Multi-LLM: produce AGENTS.md + CLAUDE.md

#### AGENTS.md

Contains all shared project context. Both `CLAUDE.md` and `GEMINI.md` reference
this file and do not duplicate its content.

```markdown
# AGENTS.md

## Project

[One paragraph. What this project does, who it is for, and the primary domain.]

## Stack

[Terse list. Format: `technology — version constraint` only where version matters.]

## Dev commands

[install, dev/start, build, test, lint, migrate — only commands actually used]

## Architecture

[Key directories and what lives in them. 1 line per directory.]
[Non-obvious patterns: e.g. "all business logic in services/, controllers are thin"]

## Business logic

[Domain entities and the rules that govern them.]
[Format: entity or concept → rule or constraint.]

## Related systems

[Only if a related system was identified. Omit entirely otherwise.]

## Conventions

[Naming, error handling, patterns enforced in the codebase.]

## Known inconsistencies

[Output from Phase 4. Omit section entirely if none found.]

## Out of scope

[Areas no agent should touch without explicit instruction.]

## Planning documents

[Output from Phase 6 — only files that exist. Omit table if none exist yet.]

| File | Purpose |
| ---- | ------- |
| …    | …       |

## Audit Config

- package_manager: <resolved>
- test_runner: <resolved>
- lint_cmd: <resolved>
- src_dirs: <resolved>
- exclude_dirs: <resolved>
- docstring_style: <resolved>

## Phase ownership

| Phase | Owner | Worktree |
| ----- | ----- | -------- |
| …     | …     | …        |

## Worktree convention

[How worktrees are structured on this project — derived from Phase 1 signals or left as template if not determinable.]
```

#### CLAUDE.md (multi-LLM)

All project context is in `AGENTS.md`.

```markdown
# CLAUDE.md

> Read AGENTS.md first. This file covers only what is specific to Claude Code.

## Development approach

TDD is required on this project. The Red/Green worktree split depends on it.

- Write no implementation before tests exist in tests/\*.
- Run the test suite after every logical change.
- Refactor only when tests are green.
- If a test appears incorrect, stop and raise it — do not work around it.

## Worktree scope

impl/_ only. Do not read, modify, or create files in tests/_.
If OVERRIDE.md exists in the project root, read it before starting —
it may authorise temporary exceptions.

## Token limit protocol

If you hit a token limit mid-task:

1. Finish the current logical unit if within 1–2 steps of completion.
2. Write HANDOFF.md to the worktree root.
3. Stop. Do not start a new task.

## Tool constraints

Bash is permitted for: grep, find, ls, mkdir, wc.
Do not run the project, install dependencies, or execute tests directly.

## Output format

[Any Claude-specific output rules detected during audit — omit if none]
```

---

## Phase 8 — Write or diff

**No existing files:** write directly. Confirm with a one-line summary of what was written.

**Existing files, full rewrite chosen:** overwrite. Show a brief summary of what changed.

**Existing files, diff review chosen:** display the proposed new content in full. Ask:

> "Ready to overwrite with the above? (yes / no / edit — paste changes)"

If they say edit, apply their changes, show the result once more, then write on confirmation.

---

## Phase 9 — Post-write instructions (multi-LLM only)

After writing `AGENTS.md` and `CLAUDE.md`, print the following:

```
AGENTS.md and CLAUDE.md have been written.

Add the following to .gitignore if not already present:
  OVERRIDE.md
  HANDOFF.md

Next step: generate GEMINI.md using the Gemini CLI custom command init-gemini-md.

To create that command, give Gemini the following brief:

---
You are creating a Gemini CLI custom command in TOML format.

Command name: init-gemini-md
Purpose: Audit an existing project and produce a GEMINI.md file that scopes
Gemini CLI's behaviour for the project. Always run after AGENTS.md has been
created by the Claude init-claude-md command.

The command must:
1. Read AGENTS.md for full project context (stack, architecture, conventions,
   src_dirs, exclude_dirs, worktree convention, phase ownership table).
2. Locate the test directory and read up to 3 existing test files to infer
   the project's test style (naming, structure, assertion patterns, imports).
3. Locate up to 3 source files to cross-reference against tests.
4. Produce GEMINI.md in the project root with exactly these sections:

   ## Purpose
   One sentence: what this file is and that AGENTS.md must be read first.

   ## Worktree scope
   tests/* for Phase 3a. No worktree for Phase 5b review pass.

   ## Development approach
   TDD rules identical to CLAUDE.md.

   ## Tool constraints
   Bash is permitted for: grep, find, ls, mkdir, wc.
   Do not run the project, install dependencies, or execute tests directly.

   ## Test style
   Inferred conventions: naming patterns, assertion library, file structure.

   ## Output format
   Any Gemini-specific output rules detected during audit — omit if none.
---
```

---

## Token optimisation

- Use `/compact` after Phase 3 on Large projects (post-subagent synthesis), and again after Phase 7 drafting before writing files.
- `disable-model-invocation: true` prevents nested model calls — do not remove this flag.
- Grep before Read in every phase. A file not Grepped is a file not read.
- Keep `CLAUDE.md` under ~150 lines (excluding `## Audit Config`). Trim aggressively. If a section has nothing non-trivial to say, omit it.
- Multi-LLM `CLAUDE.md` must not exceed 40 lines.

---

## Constraints

- Never read a file not explicitly called for by the phase logic above.
- Never use `Bash` to run the project, install dependencies, or execute tests. `Bash` is permitted only for: `find`, `wc -l`, `git log --oneline -10`, `git branch`, `grep -s`.
- If uncertain whether a file is worth reading, use `Grep` on it first.
- Total file reads across all phases must not exceed the cap. Count every read.
- Single-LLM `CLAUDE.md` should be readable in under 2 minutes. If the draft exceeds ~150 lines, trim it. `## Audit Config` does not count against this budget.
- Multi-LLM `AGENTS.md` has the same ~150 line budget for all sections except `## Audit Config` and `## Phase ownership`.
- Multi-LLM `CLAUDE.md` should not exceed 40 lines.
- On re-runs where only a specific section needs updating, use the diff review option (option 2 in Phase 0a) to limit what gets rewritten.
