# Multi-LLM-Assisted Development Workflow

## Overview

| Step | Task                                       | Primary LLM | Supporting LLM       | Interface                   |
| ---- | ------------------------------------------ | ----------- | -------------------- | --------------------------- |
| 1    | Architecture & planning                    | Claude      | Gemini (visual refs) | claude.ai web               |
| 2a   | Implementation planning                    | Claude      | —                    | claude.ai web               |
| 2b   | Pencil.dev design                          | Claude Code | —                    | Terminal + Pencil           |
| 3a   | TDD — Red (write tests)                    | Gemini CLI  | —                    | Terminal, tests/\* worktree |
| 3b   | TDD — Green + Refactor                     | Claude Code | —                    | Terminal, impl/\* worktree  |
| 3c   | Design to code (.pen → components)         | Claude Code | —                    | Terminal + Pencil MCP       |
| 4    | UI polish, responsiveness                  | Claude Code | —                    | Terminal                    |
| 5a   | Code review — correctness, security        | Claude Code | —                    | Terminal                    |
| 5b   | Code review — coverage, style, consistency | Gemini CLI  | —                    | Terminal                    |

---

# Step 1: Exploratory Planning

## What, Why, Which LLM

**Use Claude for architecture and system design.**

Claude's extended thinking excels at methodically working through complex architectural decisions — trade-offs, constraint reasoning, scope ambiguity. It is more likely to surface edge cases, ask the right clarifying questions, and produce coherent long-term plans than Gemini at this stage. It is also more honest about uncertainty.

Gemini has one legitimate role here: **ingesting large visual references and documents**. Its 2M token context window and stronger multimodal analysis makes it the better tool when your inputs are screenshots, competitor UIs, brand guidelines as images, or bulk documentation. Use it to distil those inputs into a structured brief, then bring that brief into Claude.

## Workflow

```
Visual references (screenshots, Figma exports, brand docs)
  → Gemini (analyse, extract palette, layout, component inventory)
  → structured design brief

Written requirements, scope, constraints, prior art
  → Claude (architecture, system design, trade-off analysis, scope definition)
  → architecture doc, component map, data model sketch
```

## Exploratory Conversation Approach

Architecture is best developed through conversation, not a single prompt. The recommended workflow:

1. Create a Claude Project for the engagement.
2. Run the `project-instructions-creator` skill to establish project context, output rules, and Claude's behaviour defaults for this project.
3. Have separate conversations within the project for distinct concerns — scope, architecture, data model, API design, infrastructure. Don't conflate them.
4. When a particular aspect feels well-defined, ask Claude to produce a structured MD document summarising that aspect. Review it in the conversation before exporting.
5. **Export step (critical for multi-LLM work):** copy the final MD to both your Google Drive and the repo root. Committed files are the shared ground truth that Claude Code and Gemini CLI will read. Drive is for your records; the repo is the working reference.

Canonical filenames to commit to repo root:

| Document           | Filename           |
| ------------------ | ------------------ |
| Scope definition   | `SCOPE.md`         |
| Architecture       | `ARCHITECTURE.md`  |
| Data model         | `DATA_MODEL.md`    |
| API contracts      | `API_CONTRACTS.md` |
| Design brief       | `DESIGN_BRIEF.md`  |
| Agent instructions | `AGENTS.md`        |

`AGENTS.md` references all of the above so any LLM reading it knows where to look for context.

## Tools

- **claude.ai web** — use Projects to persist context across planning sessions. Commit your architecture doc and AGENTS.md to the project knowledge base.
- **Gemini web / Gemini CLI** — for visual reference analysis only at this step.
- **Excalidraw or draw.io** — for sketching architecture diagrams to include in prompts.

---

# Step 2: Implementation Planning + Pencil.dev

## Step 2a: Implementation Planning

### What, Why, Which LLM

Architecture documents describe the system. Implementation planning turns them into a concrete task graph that multiple LLMs can execute in parallel without treading on each other.

**Do this in Claude web (Projects), not Claude Code.** The output is a planning document, not code. Claude Code is for execution.

### From Architecture to Implementation Plan

The goal is to decompose the architecture into:

- **Bounded work units** — tasks small enough that one LLM in one worktree can complete them without needing to coordinate mid-task with another LLM.
- **Explicit ownership** — each task or group of tasks is assigned to a worktree (`tests/*` or `impl/*`) and implicitly to an LLM.
- **Dependency order** — which tasks must be done before others can start. This determines sequencing across worktrees and prevents merge conflicts.
- **Interface contracts** — any boundary between tasks owned by different LLMs must be defined before either starts.

### Prompting Pattern for Implementation Planning

**Stage 1: Decomposition**

```
Read ARCHITECTURE.md, SCOPE.md, DATA_MODEL.md, and API_CONTRACTS.md.

Decompose the implementation into discrete tasks. For each task output:
- ID and title
- What it produces (file, module, API endpoint, schema migration, etc.)
- What it depends on (other task IDs or external inputs)
- Estimated complexity (S / M / L)
- Which worktree owns it: tests/* or impl/*
- Interface contract (if this task produces a boundary another task consumes)

Do not include implementation detail — only scope, dependencies, and ownership.
Group tasks by feature or domain area.
```

**Stage 2: Interface contract review**

```
Review the interface contracts you identified.
For any contract where tests/* and impl/* will work on the same boundary:
- Write the exact function/method signature
- Define input and output types
- State any invariants or error conditions the implementation must honour

Output these as a contracts table, then as a TypeScript (or Python) types
file I can commit as CONTRACTS.ts (or contracts.py).
```

**Stage 3: Sequencing**

```
Given the task list and dependency graph, produce:
1. A phased execution plan — which tasks can be parallelised across worktrees,
   which must be sequential
2. The order in which worktrees should be created and retired
3. Any merge sequence constraints (e.g. tests/* must merge before impl/*)
```

### Output

Commit the following before implementation begins:

- `IMPLEMENTATION_PLAN.md` — task list, ownership, dependencies, phasing
- `CONTRACTS.ts` (or `.py`) — all interface boundaries in code
- `AGENTS.md` — updated to reference the above and specify worktree conventions for this feature

The `IMPLEMENTATION_PLAN.md` also serves as the input CSV source for `/project:progress` (use the `task-to-progress-csv` skill to convert it).

---

## Step 2b: Pencil.dev Design

### What, Why, Which LLM

**Claude Code + Pencil MCP throughout.** The MCP server exposes tools (`batch_design`, `batch_get`, `get_screenshot`, `snapshot_layout`) that Claude Code uses to read and write `.pen` files directly.

### Workflow

```bash
wt switch -c impl/feature-name
cd ../repo-claude
claude

"Read ARCHITECTURE.md, DESIGN_BRIEF.md, and IMPLEMENTATION_PLAN.md.
Create the following components in design.pen:
- AuthForm with email, password fields, submit button
- ErrorBanner component
- LoadingSpinner
Follow the design tokens and layout grid in DESIGN_BRIEF.md."

git add design/*.pen
git commit -m "design(auth): lock auth screen components"
```

### Pencil MCP Setup

In `mcp.json` (Claude Code config):

```json
{
  "mcpServers": {
    "pencil": {
      "command": "pencil",
      "args": ["mcp"]
    }
  }
}
```

---

## Step 2c: Worktrees with Worktrunk

### What Worktrunk Does

Worktrunk (`wt`) is a thin wrapper around `git worktree` that adds lifecycle management, naming conventions, and hooks. Each worktree is an independent checkout of the repo in a sibling directory, allowing multiple LLMs to work in parallel without sharing a working tree.

| Worktree name     | Who uses it | What it contains               |
| ----------------- | ----------- | ------------------------------ |
| `tests/<feature>` | Gemini CLI  | Failing tests only (Red phase) |
| `impl/<feature>`  | Claude Code | Implementation + design files  |

### Key Commands

```bash
# Create a worktree
wt switch -c impl/auth-module
wt switch -c tests/auth-module

# List all active worktrees
wt list

# Switch to a worktree
wt switch impl/auth-module

# Remove a worktree after merging
wt remove auth-module

# Run a command in a worktree without switching
wt run impl/auth-module -- claude "Run the test suite"

# Create from a specific branch
wt switch -c impl/auth-module --branch feature/auth-module
```

### Hooks: Auto-Symlink Local Files Between Worktrees

**`.wtrunkconfig`** (commit to repo root):

```toml
[hooks]
post_create = ".worktrunk/hooks/post-create.sh"
```

**`.worktrunk/hooks/post-create.sh`**:

```bash
#!/usr/bin/env bash
# $WORKTREE_PATH and $MAIN_WORKTREE_PATH are set by worktrunk

set -euo pipefail

SHARED_FILES=(
  ".env"
  "AGENTS.md"
  "CLAUDE.md"
  "GEMINI.md"
  "OVERRIDE.md"
  "ARCHITECTURE.md"
  "SCOPE.md"
  "DESIGN_BRIEF.md"
  "IMPLEMENTATION_PLAN.md"
  "CONTRACTS.ts"
)

for file in "${SHARED_FILES[@]}"; do
  src="${MAIN_WORKTREE_PATH}/${file}"
  dst="${WORKTREE_PATH}/${file}"
  if [ -f "$src" ] && [ ! -e "$dst" ]; then
    ln -s "$src" "$dst"
    echo "Symlinked: ${file}"
  fi
done
```

```bash
chmod +x .worktrunk/hooks/post-create.sh
```

`OVERRIDE.md` is included in the symlink list so any active override is
immediately visible in all worktrees.

| Symlink (shared, read-only) | Do not symlink (worktree-specific) |
| --------------------------- | ---------------------------------- |
| `.env`                      | `node_modules/`                    |
| `AGENTS.md`                 | `dist/`, `build/`                  |
| `CLAUDE.md`, `GEMINI.md`    | `.next/`, `__pycache__/`           |
| `OVERRIDE.md`               | Any generated or compiled output   |
| All planning `.md` files    | Worktree's git history and index   |
| `CONTRACTS.ts`              |                                    |

### Merging Worktrees

Always merge `tests/*` before `impl/*`.

```bash
cd ~/project
git fetch origin
git diff main origin/tests/auth-module
git diff main origin/impl/auth-module
git merge origin/tests/auth-module
git merge origin/impl/auth-module
wt remove auth-module
```

---

# Step 3: TDD + Design to Code

## 3a — Red Phase (Gemini writes failing tests)

```bash
cd ../repo-gemini
gemini "Read AGENTS.md, GEMINI.md, IMPLEMENTATION_PLAN.md, CONTRACTS.ts,
and tests/user.test.ts.
Write failing tests for the auth module.
Cover happy path, boundary values, and all error states in CONTRACTS.ts.
Match the existing test style exactly.
Do NOT implement anything — tests must fail on completion."

git add tests/
git commit -m "test(auth): add failing tests for auth module"
git push origin tests/feature-name
```

## 3b — Green + Refactor Phase (Claude Code makes tests pass)

```bash
cd ../repo-claude
git fetch origin
git merge origin/tests/feature-name

claude "Read AGENTS.md, CLAUDE.md, IMPLEMENTATION_PLAN.md, and CONTRACTS.ts.
Run the test suite. Make all failing tests pass.
Do NOT modify any file in tests/.
If a test appears incorrect, stop and explain — do not work around it."

claude "Tests are passing. Refactor for clarity and maintainability.
Run the suite after each logical change."
```

## 3c — Design to Code (.pen → Components)

```bash
claude "Convert design.pen to React components.
Use the Pencil-to-Code skill.
Map all design tokens to Tailwind @theme config.
Generate type-safe TypeScript components.
Validate against the .pen file via screenshot comparison."
```

---

# Step 4: UI Polish and Responsiveness

**Claude Code throughout.**

```bash
claude "Review all generated components against DESIGN_BRIEF.md.

Polish tasks:
1. Verify spacing matches the 8pt grid system
2. Check typography scale consistency
3. Ensure all interactive states are implemented (hover, focus, disabled, loading)
4. Make all components responsive:
   - Mobile: < 768px
   - Tablet: 768–1024px
   - Desktop: > 1024px
5. Validate colour contrast meets WCAG AA

Do not change component logic. UI and layout only."
```

---

# Step 5: Code Review

## 5a — Correctness and Security (Claude Code)

```bash
git diff main..impl/feature-name > /tmp/review.diff

claude "Review /tmp/review.diff for:
1. Logic errors and off-by-one mistakes
2. Unhandled edge cases
3. Security issues: injection, auth bypass, data exposure, insecure defaults
4. API contract violations against CONTRACTS.ts
5. Error handling gaps

For each finding: file, line range, issue, severity (critical/high/medium/low),
suggested fix."
```

## 5b — Coverage, Style, Consistency (Gemini CLI)

```bash
git diff main..impl/feature-name > /tmp/review.diff

gemini "Read AGENTS.md and the full codebase. Then review /tmp/review.diff.

1. Test coverage: what cases are untested? what branches are missing?
2. Style: does this match the patterns in the rest of the codebase?
3. Consistency: naming, structure, abstractions — does this fit?
4. Dead code or unnecessary complexity?

Flag any deviation from the contracts defined in CONTRACTS.ts."
```

## Merge After Review

```bash
cd ~/project
git fetch origin
git merge origin/tests/feature-name
git merge origin/impl/feature-name
wt remove feature-name
```

---

# Project Audit: Two-Pass Model

In multi-LLM projects the audit runs in two sequential passes.

## Pass 1: Claude Code (`/project:audit`)

Detects multi-LLM mode by checking for `AGENTS.md`. Runs Claude-scoped subagents:

- **A** — Dependencies + Secrets
- **B** — Error Handling + Logical Errors
- **C** — Tech Debt + Code Quality

Produces:

- `audit-reports/<timestamp>/AUDIT-SUMMARY.md` — Test Coverage and Comment/Doc Compliance rows marked `Gemini pass pending`
- `audit-reports/<timestamp>/gemini-audit-prompt.md` — self-contained prompt for Pass 2

## Pass 2: Gemini CLI (`/project:audit-gemini`)

Runs **D** — Test Coverage + Comment/Doc Compliance. Updates `AUDIT-SUMMARY.md`
in place. Produces `D-test-docs.md` in the same run folder.

```bash
/project:audit
gemini < audit-reports/<timestamp>/gemini-audit-prompt.md
```

---

# Handling Token Limits and Cross-LLM Handoffs

Token limits mid-task are normal. The scope rules in AGENTS.md exist to prevent
silent conflicts, not to make recovery impossible. Two conventions handle this
without relaxing the rules globally.

## HANDOFF.md — mandatory stopping convention

When either LLM stops mid-task for any reason — token limit, session end, or
explicit handoff — it writes `HANDOFF.md` to the worktree root before stopping.
This applies whether or not a cross-LLM handoff is intended.

```markdown
# Handoff — <worktree> — <YYYY-MM-DD HH:MM IST>

## Stopped by

<Claude Code | Gemini CLI> — <reason: token limit | session end | explicit handoff>

## State at handoff

- Completed: <list of files or tasks fully done>
- In progress: <file or task currently partial — describe exact state>
- Not started: <remaining tasks from IMPLEMENTATION_PLAN.md>

## Last action

<One sentence: the last thing written or run>

## Next step

<Exactly what the continuing session should do first>

## Safe to continue

<yes | no — if no, explain what needs resolving before continuing>
```

The continuing LLM reads `HANDOFF.md` before doing anything else. If "Safe to
continue" is no, run `git diff` and resolve the inconsistency before proceeding.

## OVERRIDE.md — explicit user-controlled scope expansion

When you need one LLM to work outside its normal worktree scope, create
`OVERRIDE.md` in the project root. Both LLMs check for it at the start of every
task. **You create this file. The LLM does not.**

Delete it when the override task is complete. Do not commit it.

### Example: Claude Code completing tests after Gemini CLI token limit

```markdown
# OVERRIDE.md

## Reason

Gemini CLI token limit reached mid-task on tests/payment-module.
Claude Code completing remaining test files.

## Read first

tests/payment-module/HANDOFF.md

## Authorised scope expansion

Claude Code may read and write:

- tests/payment-module/refund.test.ts ← not started per HANDOFF.md
- tests/payment-module/webhook.test.ts ← not started per HANDOFF.md

Claude Code may read (no writes):

- tests/payment-module/checkout.test.ts ← completed by Gemini, reference only

## Conditions

- Read HANDOFF.md before starting.
- Do not modify any file not listed above.
- Tests must follow the same style as checkout.test.ts.
- Tests must fail on creation — do not implement anything.
- Write HANDOFF.md to tests/payment-module/ when done or stopping early.
- Delete OVERRIDE.md when all authorised files are complete.

## Authorised by

<your name> — <date>
```

### Example: Gemini CLI completing implementation after Claude Code token limit

```markdown
# OVERRIDE.md

## Reason

Claude Code token limit reached mid-task on impl/auth-module.
Gemini CLI completing remaining implementation files.

## Read first

impl/auth-module/HANDOFF.md

## Authorised scope expansion

Gemini CLI may read and write:

- src/auth/refresh.ts ← not started per HANDOFF.md
- src/auth/revoke.ts ← not started per HANDOFF.md

Gemini CLI may read (no writes):

- src/auth/login.ts ← completed by Claude Code, reference only
- src/auth/token.ts ← completed by Claude Code, reference only
- tests/auth/ ← reference for what must pass

## Conditions

- Read HANDOFF.md before starting.
- Do not modify any file not listed above.
- Run the test suite after each file. Tests must stay green.
- Do not modify any file in tests/.
- Write HANDOFF.md to impl/auth-module/ when done or stopping early.
- Delete OVERRIDE.md when all authorised files are complete.

## Authorised by

<your name> — <date>
```

### OVERRIDE.md rules

- List every authorised file explicitly. No wildcards.
- Separate read+write from read-only entries.
- Always reference the relevant HANDOFF.md.
- Always include the deletion condition.
- Never commit OVERRIDE.md. Add to `.gitignore`.
- If the override task itself hits a token limit, write HANDOFF.md before
  stopping and update OVERRIDE.md to reflect remaining files only.

Add to `.gitignore`:

```
OVERRIDE.md
HANDOFF.md
```

---

# File Structure Reference

## AGENTS.md (multi-LLM projects — shared ground truth)

Generated by `init-claude-md` when multi-LLM mode is selected. Contains everything
both LLMs need. Both `CLAUDE.md` and `GEMINI.md` defer to it for project context.

```markdown
# AGENTS.md

## Project

[domain, purpose, client/internal]

## Stack

[technologies and version constraints]

## Architecture

[key directories and patterns]

## Business logic

[domain entities and rules]

## Related systems

[integrated repos or services, if any]

## Dev commands

[install, dev, build, test, lint, migrate]

## Conventions

[naming, error handling, patterns enforced in the codebase]

## Known inconsistencies

[discrepancies found during audit — omit if none]

## Out of scope

[areas no agent should touch without explicit instruction]

## Planning documents

[only files that exist at time of generation]

| Document            | Filename               |
| ------------------- | ---------------------- |
| Scope definition    | SCOPE.md               |
| Architecture        | ARCHITECTURE.md        |
| Data model          | DATA_MODEL.md          |
| API contracts       | API_CONTRACTS.md       |
| Design brief        | DESIGN_BRIEF.md        |
| Implementation plan | IMPLEMENTATION_PLAN.md |
| Interface contracts | CONTRACTS.ts           |

## Phase ownership

| Phase | Owner       | Worktree | Scope                               |
| ----- | ----------- | -------- | ----------------------------------- |
| 3a    | Gemini CLI  | tests/\* | Write failing tests only            |
| 3b    | Claude Code | impl/\*  | Make tests pass, refactor           |
| 3c    | Claude Code | impl/\*  | .pen → components                   |
| 4     | Claude Code | impl/\*  | UI polish, no logic changes         |
| 5a    | Claude Code | impl/\*  | Correctness and security review     |
| 5b    | Gemini CLI  | —        | Coverage, style, consistency review |

## Hard rules (all agents)

- Do not modify files outside your designated worktree scope.
- Do not install dependencies without confirmation.
- Do not touch .env files.
- Do not deviate from CONTRACTS.ts without stopping and raising it explicitly.
- If you need to touch a file outside your scope, stop. Do not work around it.
- If you cannot complete a task due to token limits or session constraints, write
  HANDOFF.md to the worktree root before stopping. Document what was completed,
  what is in progress, what remains, and whether it is safe to continue.
- If OVERRIDE.md exists in the project root, read it before starting any task.
  You may write to files explicitly listed in OVERRIDE.md regardless of your
  normal worktree scope. Do not exceed what is listed. Delete OVERRIDE.md when
  the override task is complete.

## Audit Config

- package_manager: <resolved>
- test_runner: <resolved>
- lint_cmd: <resolved>
- src_dirs: <resolved>
- exclude_dirs: <resolved>
- docstring_style: <resolved>
```

## CLAUDE.md (multi-LLM projects — Claude-specific)

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

## GEMINI.md (multi-LLM projects — Gemini-specific)

Generated by the `init-gemini-md` Gemini CLI custom command.

```markdown
# GEMINI.md

> Read AGENTS.md first. This file covers only what is specific to Gemini CLI.

## Worktree scope

tests/\* for Phase 3a. No worktree for Phase 5b review pass.
If OVERRIDE.md exists in the project root, read it before starting —
it may authorise temporary exceptions.

## Token limit protocol

If you hit a token limit mid-task:

1. Finish the current logical unit if within 1–2 steps of completion.
2. Write HANDOFF.md to the worktree root.
3. Stop. Do not start a new task.

## Phase 3a — Test authoring

[What to read before starting]
[Test style rules inferred from existing tests]
Hard rules:

- Do not implement anything.
- Tests must fail on creation.
- Do not modify any file outside tests/\*.
- Match existing test style exactly.
- Cover: happy path, boundary values, all error states in CONTRACTS.ts.

## Phase 5b — Review pass

[What to read and diff]
Output format: file, line range, issue, severity, suggested fix.
Review scope: test coverage gaps, style drift, naming consistency,
dead code, deviations from CONTRACTS.ts.
Do not modify any files — review output only.

## Hard rules (all phases)

- Do not modify files outside designated scope.
- Do not install dependencies.
- Do not touch .env files.
- Do not deviate from CONTRACTS.ts without stopping and raising it explicitly.
```

## HANDOFF.md (per worktree — not committed)

Written by either LLM when stopping mid-task. See
[Handling Token Limits and Cross-LLM Handoffs](#handling-token-limits-and-cross-llm-handoffs)
for the full template.

## OVERRIDE.md (project root — not committed)

Created by the user to authorise temporary scope expansion. See
[Handling Token Limits and Cross-LLM Handoffs](#handling-token-limits-and-cross-llm-handoffs)
for examples and rules.

---

# Gemini CLI Custom Command Briefs

## init-gemini-md

```
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
   If OVERRIDE.md exists in the project root, read it before starting any
   task — it may authorise temporary exceptions to worktree scope.

   ## Token limit protocol
   If you hit a token limit mid-task:
   1. Finish the current logical unit if within 1-2 steps of completion.
   2. Write HANDOFF.md to the worktree root documenting: what was completed,
      what is in progress, what remains, and whether it is safe to continue.
   3. Stop. Do not start a new task.

   ## Phase 3a — Test authoring
   - What to read before starting (list the exact files)
   - Inferred test style rules (from the test files read)
   - Hard rules:
     - Do not implement anything
     - Tests must fail on creation
     - Do not modify any file outside tests/*
     - Match existing test style exactly
     - Cover: happy path, boundary values, all error states in CONTRACTS.ts

   ## Phase 5b — Review pass
   - What to read before starting (AGENTS.md, the diff, full codebase)
   - Output format: file, line range, issue, severity, suggested fix
   - Review scope: test coverage gaps, style drift, naming consistency,
     dead code, deviations from CONTRACTS.ts
   - What not to touch: no file modifications, review output only

   ## Hard rules (all phases)
   - Do not modify files outside designated scope
   - Do not install dependencies
   - Do not touch .env files
   - Do not deviate from CONTRACTS.ts without stopping and raising it

Output rules:
- GEMINI.md must be accurate to this project, not generic.
- Test style rules must be inferred from actual test files, not assumed.
- If no test files exist yet, state that explicitly and omit inferred rules.
- Cap file reads at 10 total.
```

## project-audit-gemini

```
You are creating a Gemini CLI custom command in TOML format.

Command name: project-audit-gemini
Purpose: Run the Gemini-scoped portion of a project audit. Always run after
the Claude pass (/project:audit) has completed. Reads the existing
AUDIT-SUMMARY.md from the most recent Claude pass and appends findings to it.

The command must:
1. Locate the most recent audit-reports/YYYYMMDD_hhmm/ subfolder.
2. Read AUDIT-SUMMARY.md from that folder.
3. Read AGENTS.md for project context (stack, src_dirs, exclude_dirs).
   Fall back to CLAUDE.md Audit Config if AGENTS.md is absent.
4. Run test coverage analysis using the detected test runner.
5. Run comment/doc compliance analysis (JSDoc / Google docstrings / XML doc).
6. Produce D-test-docs.md in the same run folder:
   ## Summary / ## Findings (Severity | File/Area | Description) /
   ## Metrics / ## Top Recommendations (max 5)
7. Update AUDIT-SUMMARY.md in place:
   - Replace Test Coverage and Comment/Doc Compliance rows with actual counts.
   - Replace "Gemini pass pending" notes with actual findings summary.
   - Update Baseline Metrics: test coverage %, doc compliance %, test file count.
   - Append ## Gemini Pass: date/time, model, files read, token usage.

Findings Overview columns: Domain | Critical | High | Medium | Low | Notes
Use — (em dash) for Critical and High on Test Coverage and Comment/Doc Compliance.

Output rules:
- Never modify AUDIT-SUMMARY.md sections other than those listed above.
- Never run the project or install dependencies.
- Stay within src_dirs for all file reads.
- Use the same severity vocabulary as the Claude pass: critical/high/medium/low.
```

---

# Full Tool Reference

| Tool                            | Role                                            | Install                                          |
| ------------------------------- | ----------------------------------------------- | ------------------------------------------------ |
| **claude.ai** (web, Projects)   | Steps 1, 2a planning                            | —                                                |
| **Claude Code**                 | Steps 2b, 3b, 3c, 4, 5a                         | `npm i -g @anthropic-ai/claude-code`             |
| **Gemini CLI**                  | Steps 1 (visual refs), 3a, 5b                   | `npm i -g @google/gemini-cli`                    |
| **Pencil.dev**                  | Steps 2b–3c design canvas                       | pencil.dev (free, VS Code / Cursor / standalone) |
| **Pencil-to-Code skill**        | Step 3c .pen → React                            | mcpmarket.com                                    |
| **Worktrunk** (`wt`)            | Worktree lifecycle                              | `pip install worktrunk`                          |
| **agentic.nvim**                | nvim ACP client — Claude + Gemini in one editor | lazy.nvim                                        |
| **git-worktree-runner** (`gtr`) | Worktree creation with auto-symlink             | `npm i -g @coderabbitai/git-worktree-runner`     |
