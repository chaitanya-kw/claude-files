---
name: project-audit
description: Full baseline audit of the current branch. In single-LLM projects, covers all domains. In multi-LLM projects (detected via AGENTS.md), covers only Claude-scoped domains (deps, error handling, tech debt, security). Supports --full for a complete OWASP scan. Reads AGENTS.md (multi-LLM) or CLAUDE.md (single-LLM) Audit Config for stack overrides.
allowed-tools: Read, Glob, Grep, Bash, Task
disable-model-invocation: true
---

# Project Audit

Perform a full or Claude-scoped audit of the current branch. This command audits
the entire working tree — it does NOT operate on diffs. The branch to audit must
be checked out before running.

**Usage:** `/project:audit` or `/project:audit --full` (full OWASP scan instead of lite)

---

## Step 0 — Mode detection

Before any tooling checks, determine the project's LLM mode:

```bash
if [ -f "AGENTS.md" ]; then
  IS_MULTI_LLM=true
  CONFIG_FILE="AGENTS.md"
  echo "Multi-LLM project detected (AGENTS.md found)."
  echo "Running Claude-scoped pass. Subagent D (test coverage + doc compliance)"
  echo "will be handled by the Gemini audit command."
else
  IS_MULTI_LLM=false
  CONFIG_FILE="CLAUDE.md"
  echo "Single-LLM project detected. Running full audit."
fi
```

---

## Step 1 — Tool pre-flight

Check every tool required by this command. Attempt auto-install where possible.
If a required tool cannot be installed, print a clear install instruction, then STOP.

### 1a. Quick stack probe

```bash
IS_NODE=0; IS_PYTHON=0; IS_DOTNET=0
[ -f "package.json" ]                                                      && IS_NODE=1
{ [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || [ -f "Pipfile" ]; } && IS_PYTHON=1
find . -maxdepth 3 \( -name "*.csproj" -o -name "*.sln" \) 2>/dev/null \
  | grep -q .                                                               && IS_DOTNET=1
```

### 1b. git

```bash
command -v git >/dev/null 2>&1 \
  || { echo "ABORT: git is not installed. Install git and re-run."; exit 1; }
```

### 1c. Node runtime (Node projects only)

```bash
if [ "$IS_NODE" = "1" ]; then
  command -v node >/dev/null 2>&1 \
    || { echo "ABORT: node not found. Install Node.js (https://nodejs.org) and re-run."; exit 1; }
  command -v npm >/dev/null 2>&1 \
    || { echo "ABORT: npm not found. Comes bundled with Node.js."; exit 1; }
fi
```

### 1d. Python runtime and pip-audit (Python projects only)

```bash
if [ "$IS_PYTHON" = "1" ]; then
  command -v python3 >/dev/null 2>&1 \
    || { echo "ABORT: python3 not found."; exit 1; }

  if ! command -v pip-audit >/dev/null 2>&1; then
    pip install pip-audit --break-system-packages 2>/dev/null \
      || pip3 install pip-audit 2>/dev/null
    command -v pip-audit >/dev/null 2>&1 \
      || { echo "ABORT: pip-audit could not be installed. Run: pip install pip-audit"; exit 1; }
  fi
fi
```

### 1e. dotnet CLI (.NET projects only)

```bash
if [ "$IS_DOTNET" = "1" ]; then
  command -v dotnet >/dev/null 2>&1 \
    || { echo "ABORT: dotnet CLI not found. Install: https://dot.net"; exit 1; }
fi
```

### 1f. semgrep

```bash
if ! command -v semgrep >/dev/null 2>&1; then
  pip install semgrep --break-system-packages 2>/dev/null \
    || pip3 install semgrep 2>/dev/null \
    || brew install semgrep 2>/dev/null
  command -v semgrep >/dev/null 2>&1 \
    || {
      echo "ABORT: semgrep could not be installed."
      echo "  Option A (pip):  pip install semgrep"
      echo "  Option B (brew): brew install semgrep"
      echo "  Docs: https://semgrep.dev/docs/getting-started/quickstart"
      exit 1
    }
fi
echo "semgrep: $(semgrep --version)"
```

### 1g. claude-security-audit

```bash
SEC_AUDIT_CMD=""
[ -f "$HOME/.claude/commands/security-audit.md" ] \
  && SEC_AUDIT_CMD="$HOME/.claude/commands/security-audit.md"
[ -f ".claude/commands/security-audit.md" ] \
  && SEC_AUDIT_CMD=".claude/commands/security-audit.md"

if [ -z "$SEC_AUDIT_CMD" ]; then
  echo "ABORT: claude-security-audit is not installed."
  echo "  git clone https://github.com/afiqiqmal/claude-security-audit /tmp/cc-sec-audit"
  echo "  mkdir -p ~/.claude/commands"
  echo "  cp /tmp/cc-sec-audit/.claude/commands/security-audit.md ~/.claude/commands/"
  echo "  cp -r /tmp/cc-sec-audit/references ~/.claude/security-audit-references"
  exit 1
fi
echo "claude-security-audit: $SEC_AUDIT_CMD"
```

### 1h. Linter check (warn only)

```bash
LINTER_FOUND=0
if [ "$IS_NODE" = "1" ]; then
  for f in .eslintrc.js .eslintrc.cjs .eslintrc.json .eslintrc.yml \
            eslint.config.js eslint.config.mjs eslint.config.cjs; do
    [ -f "$f" ] && LINTER_FOUND=1 && break
  done
fi
if [ "$IS_PYTHON" = "1" ]; then
  command -v ruff   >/dev/null 2>&1 && LINTER_FOUND=1
  command -v pylint >/dev/null 2>&1 && LINTER_FOUND=1
fi
if [ "$IS_DOTNET" = "1" ]; then LINTER_FOUND=1; fi
if [ "$LINTER_FOUND" = "0" ]; then
  echo "WARNING: No linter detected. Lint step will produce no output."
fi
```

### 1i. Pre-flight summary

```
Pre-flight complete:
  Mode               MULTI-LLM (Claude pass only) | SINGLE-LLM (full audit)
  Config file        AGENTS.md | CLAUDE.md
  git                OK
  node / npm         OK | N/A
  python3            OK | N/A
  pip-audit          OK | N/A
  dotnet             OK | N/A
  semgrep            OK  (<version>)
  security-audit     OK
  linter             OK | WARN (no config found)
```

Run `/compact` before Step 2.

---

## Step 2 — Repository state and config

```bash
git rev-parse --is-inside-work-tree 2>/dev/null \
  || { echo "ABORT: not inside a git repository."; exit 1; }

BRANCH=$(git branch --show-current)
COMMIT=$(git log -1 --format="%H %s %ad" --date=short)
DIRTY=$(git status --short)
[ -n "$DIRTY" ] && echo "WARNING: Uncommitted changes present. Audit includes unstaged modifications."

AUDIT_TS=$(TZ='Asia/Kolkata' date +%Y%m%d_%H%M)
AUDIT_DIR="audit-reports/${AUDIT_TS}"
mkdir -p "${AUDIT_DIR}"
echo "Output dir: ${AUDIT_DIR}"
```

Read `$CONFIG_FILE` from the project root. Extract `## Audit Config`:

```
Recognised keys:
  package_manager   npm | yarn | pnpm | pip | dotnet | cargo
  test_runner       jest | vitest | pytest | dotnet-test
  lint_cmd          <full shell command>
  src_dirs          src,app,lib,api   (comma-separated, relative to repo root)
  exclude_dirs      node_modules,.next,dist,build,bin,obj
  docstring_style   jsdoc | google | numpy | sphinx
```

Defaults:

- `SRC_DIRS` = `src,app,components,lib,api,server,services,handlers,controllers,utils`
- `EXCLUDE_DIRS` = `node_modules,.next,.nuxt,dist,build,bin,obj,coverage,.git,__pycache__`
- `DOCSTRING_STYLE` = `jsdoc` for Node, `google` for Python

```bash
GREP_EXCLUDES=$(echo "$EXCLUDE_DIRS" | tr ',' '\n' \
  | sed 's/^/--exclude-dir=/' | tr '\n' ' ')
```

Write all resolved config values to `${AUDIT_DIR}/00-config.txt`.

Run `/compact` before Step 3. Surviving variables: `AUDIT_DIR`, `AUDIT_TS`,
`BRANCH`, `COMMIT`, `IS_NODE`, `IS_PYTHON`, `IS_DOTNET`, `SRC_DIRS`,
`EXCLUDE_DIRS`, `GREP_EXCLUDES`, `PKG_MGR`, `TEST_RUNNER`, `LINT_CMD`,
`LINTER_FOUND`, `SCAN_MODE`, `IS_MULTI_LLM`, `CONFIG_FILE`.

---

## Step 3 — Automated tooling (shell subagent)

Spawn one subagent using the `Task` tool with Bash access. Pass all resolved
variables as explicit context in the prompt.

The subagent runs the commands below sequentially and writes each output file
to `${AUDIT_DIR}/`. It must end its response with:
`"Step 3 complete. Output written to <AUDIT_DIR>."`

### 3a. Dependency vulnerability scan

```bash
if [ "$IS_NODE" = "1" ]; then
  [ -z "$PKG_MGR" ] && PKG_MGR="npm"
  $PKG_MGR audit --json    > "${AUDIT_DIR}/deps-vuln.json"     2>&1
  $PKG_MGR outdated --json > "${AUDIT_DIR}/deps-outdated.json" 2>&1
fi

if [ "$IS_PYTHON" = "1" ]; then
  pip-audit --output json -o "${AUDIT_DIR}/deps-vuln.json"
  pip list --outdated --format json > "${AUDIT_DIR}/deps-outdated.json" 2>&1
fi

if [ "$IS_DOTNET" = "1" ]; then
  dotnet list package --vulnerable --format json > "${AUDIT_DIR}/deps-vuln.json" 2>&1
  dotnet list package --outdated                 > "${AUDIT_DIR}/deps-outdated.txt" 2>&1
fi
```

### 3b. semgrep static analysis

```bash
semgrep scan --config=auto \
  $(echo "$EXCLUDE_DIRS" | tr ',' '\n' | sed 's/^/--exclude=/' | tr '\n' ' ') \
  --json -o "${AUDIT_DIR}/semgrep.json" . 2>"${AUDIT_DIR}/semgrep-errors.txt"
echo "exit: $?" >> "${AUDIT_DIR}/semgrep-errors.txt"
```

### 3c. Linter

```bash
if [ -n "$LINT_CMD" ]; then
  eval "$LINT_CMD" > "${AUDIT_DIR}/lint.txt" 2>&1
elif [ "$IS_NODE" = "1" ] && [ "$LINTER_FOUND" = "1" ]; then
  npx eslint . --format compact > "${AUDIT_DIR}/lint.txt" 2>&1
elif command -v ruff >/dev/null 2>&1; then
  ruff check . > "${AUDIT_DIR}/lint.txt" 2>&1
elif command -v pylint >/dev/null 2>&1; then
  pylint $(find ${SRC_DIRS//,/ } -name "*.py" 2>/dev/null | head -100) \
    > "${AUDIT_DIR}/lint.txt" 2>&1
else
  echo "SKIP: no linter available" > "${AUDIT_DIR}/lint.txt"
fi
```

### 3d. Test coverage (single-LLM only)

```bash
if [ "$IS_MULTI_LLM" = "false" ]; then
  case "$TEST_RUNNER" in
    jest)
      npx jest --coverage --coverageReporters=text-summary --passWithNoTests \
        2>&1 | tail -25 > "${AUDIT_DIR}/coverage.txt" ;;
    vitest)
      npx vitest run --coverage 2>&1 | tail -25 > "${AUDIT_DIR}/coverage.txt" ;;
    pytest)
      pytest --cov --cov-report=term-missing 2>&1 | tail -35 > "${AUDIT_DIR}/coverage.txt" ;;
    dotnet-test)
      dotnet test --collect:"XPlat Code Coverage" 2>&1 | tail -20 \
        > "${AUDIT_DIR}/coverage.txt" ;;
    *)
      echo "SKIP: no test runner configured" > "${AUDIT_DIR}/coverage.txt" ;;
  esac
else
  echo "SKIP: test coverage handled by Gemini audit command" \
    > "${AUDIT_DIR}/coverage.txt"
fi
```

### 3e. Code pattern grep scans

```bash
# Silent errors / swallowed exceptions
grep -rn $GREP_EXCLUDES \
  -e '\.catch(\s*)' \
  -e 'catch\s*([^)]*)\s*{\s*}' \
  -e 'catch\s*([^)]*)\s*{\s*//' \
  -e 'except:\s*$' \
  -e 'except Exception:\s*$' \
  -e 'except\s*:\s*pass' \
  -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-silent-errors.txt"

# Hardcoded credentials
grep -rn $GREP_EXCLUDES \
  -e 'password\s*=\s*["'"'"'][^"'"'"']\+["'"'"']' \
  -e 'secret\s*=\s*["'"'"'][^"'"'"']\+["'"'"']' \
  -e 'api_key\s*=\s*["'"'"'][^"'"'"']\+["'"'"']' \
  -e 'token\s*=\s*["'"'"'][^"'"'"']\+["'"'"']' \
  --include="*.ts" --include="*.js" --include="*.py" \
  -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-secrets.txt"

# Debug output leaks
grep -rn $GREP_EXCLUDES \
  -e 'console\.log\|console\.warn\|console\.error\|console\.debug' \
  -e 'print(\|pprint(\|logging\.debug(' \
  -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-debug-output.txt"

# Tech debt markers
grep -rn $GREP_EXCLUDES \
  -e 'TODO\|FIXME\|HACK\|XXX\|NOSONAR\|WORKAROUND\|TEMP\b\|BUG:' \
  -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-tech-debt.txt"

# TypeScript type safety bypasses
grep -rn $GREP_EXCLUDES \
  -e 'as any\b' -e ': any\b' -e '@ts-ignore' -e '@ts-nocheck' \
  --include="*.ts" --include="*.tsx" \
  -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-type-safety.txt"

# Structural logical error hints
grep -rn $GREP_EXCLUDES \
  -e 'if\s*(.*[^=!<>]=[^=].*)' \
  -e '\bNaN\b.*==.*\bNaN\b' \
  -e 'for\s*.*i\s*<=\s*.*\.length' \
  -e '[^!]==[[:space:]]*null[[:space:]]*&&\|==[[:space:]]*undefined[[:space:]]*&&' \
  --include="*.ts" --include="*.js" --include="*.py" \
  -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-logical-hints.txt"

# Async hints (unhandled .then without .catch)
grep -rn $GREP_EXCLUDES \
  -e '\.then(' \
  --include="*.ts" --include="*.js" \
  -- $SRC_DIRS 2>/dev/null \
  | grep -v '\.catch(' | head -200 > "${AUDIT_DIR}/pattern-async-hints.txt"

# Doc/comment patterns — single-LLM only
# In multi-LLM projects these are handled by the Gemini audit command
if [ "$IS_MULTI_LLM" = "false" ]; then
  grep -rn $GREP_EXCLUDES \
    -e '^export\s\+\(function\|const\|class\|async\|default\|type\|interface\)' \
    --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
    -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-exports-js.txt"

  grep -rn $GREP_EXCLUDES \
    -e '/\*\*' \
    --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
    -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-jsdoc-present.txt"

  grep -rn $GREP_EXCLUDES \
    -e '^def \|^    def \|^class ' \
    --include="*.py" \
    -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-exports-py.txt"

  grep -rn $GREP_EXCLUDES \
    -e '"""' \
    --include="*.py" \
    -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-docstrings-present.txt"

  grep -rn $GREP_EXCLUDES \
    -e '^\s*Args:\|^\s*Returns:\|^\s*Raises:\|^\s*Yields:\|^\s*Note:\|^\s*Example:' \
    --include="*.py" \
    -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-google-docstrings.txt"

  grep -rn $GREP_EXCLUDES \
    -e '^\s*///' \
    --include="*.cs" \
    -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-xmldoc-present.txt"

  grep -rn $GREP_EXCLUDES \
    -e '^\s*public\s' \
    --include="*.cs" \
    -- $SRC_DIRS 2>/dev/null > "${AUDIT_DIR}/pattern-exports-cs.txt"
fi
```

### 3f. Codebase metrics

```bash
find . -type f \
  \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \
     -o -name "*.py" -o -name "*.cs" -o -name "*.rs" \) \
  $(echo "$EXCLUDE_DIRS" | tr ',' '\n' | sed 's|^|-not -path ".*/|; s|$|/*"|' | tr '\n' ' ') \
  | xargs wc -l 2>/dev/null | sort -rn | head -20 > "${AUDIT_DIR}/metrics-loc.txt"

find . -type f \
  $(echo "$EXCLUDE_DIRS" | tr ',' '\n' | sed 's|^|-not -path ".*/|; s|$|/*"|' | tr '\n' ' ') \
  | sed 's/.*\.//' | sort | uniq -c | sort -rn > "${AUDIT_DIR}/metrics-file-types.txt"

find . -type f \
  \( -name "*.test.*" -o -name "*.spec.*" -o -name "test_*.py" -o -name "*_test.py" \) \
  2>/dev/null | wc -l > "${AUDIT_DIR}/metrics-test-files.txt"

find ${SRC_DIRS//,/ } -type f \
  \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \
     -o -name "*.py" -o -name "*.cs" \) \
  2>/dev/null | wc -l > "${AUDIT_DIR}/metrics-source-files.txt"
```

---

## Step 4 — Security scan (claude-security-audit)

Run after the Step 3 subagent returns. Before starting Step 4, run `/compact`.
The Step 3 shell output is entirely on disk.

```bash
SCAN_MODE="--lite"
echo "$ARGUMENTS" | grep -q "\-\-full" && SCAN_MODE=""
```

Invoke `/security-audit $SCAN_MODE`. Copy report:

```bash
cp security-audit-report.md "${AUDIT_DIR}/security-audit.md" 2>/dev/null \
  || echo "WARNING: security-audit-report.md not found after scan." \
       > "${AUDIT_DIR}/security-audit.md"
```

Run `/compact` before Step 5. Surviving state: `AUDIT_DIR`, `AUDIT_TS`,
`BRANCH`, `COMMIT`, `IS_MULTI_LLM`.

---

## Step 5 — Parallel LLM analysis

Issue all subagent Task calls in a single turn. In multi-LLM mode issue A, B, C
only. In single-LLM mode issue A, B, C, D.

Each subagent uses this report template:

```
## Summary
One paragraph.

## Findings
| Severity | File / Area | Description |
|----------|-------------|-------------|

## Metrics
(numbers only — used for baseline diff)

## Top Recommendations
Max 5 items, ordered by priority.
```

### Subagent A — Dependencies + Secrets

**Reads:** `deps-vuln.json`, `deps-outdated.json` or `deps-outdated.txt`,
`pattern-secrets.txt`

- CVEs: group by critical / high / medium / low. Note direct vs transitive.
- Outdated: flag packages more than 1 major version behind.
- Secrets: exclude test files and `*.example` / `*.sample`. Flag apparent real
  credentials in non-test files.

Metrics: critical CVE count, high CVE count, total vulnerable packages,
packages >1 major behind, suspected hardcoded secrets.

**Output:** `${AUDIT_DIR}/A-deps-secrets.md`

### Subagent B — Error Handling + Logical Errors

**Reads:** `pattern-silent-errors.txt`, `pattern-async-hints.txt`,
`pattern-logical-hints.txt`, `semgrep.json` (error-handling and correctness
categories only)

Then read up to 30 source files with the highest hit concentration.

**Error handling:** empty catch blocks, swallowed exceptions, unhandled promise
rejections, silent null/undefined returns, missing error propagation in async chains.

**Logical errors:** assignment inside conditional, NaN compared with `==`/`===`,
off-by-one in loops, loose nullish checks, dead branches, unreachable code after
return/throw, mixed return types, boolean logic inversions.

Metrics: silent error pattern count, async issues, structural logical issues.

**Output:** `${AUDIT_DIR}/B-error-logic.md`

### Subagent C — Tech Debt + Code Quality

**Reads:** `pattern-tech-debt.txt`, `pattern-debug-output.txt`,
`pattern-type-safety.txt`, `lint.txt`

- Tech debt: cluster by directory. Top 3 density areas. Flag deferred
  security or correctness work specifically.
- Debug leaks: flag outside test files.
- Type safety: count `as any`, `@ts-ignore`, `@ts-nocheck`.
- Lint: summarise top 5 recurring rule IDs with file distribution.

Metrics: total debt markers, debug leaks in non-test files, type bypass count,
lint error count, lint warning count.

**Output:** `${AUDIT_DIR}/C-tech-debt.md`

### Subagent D — Test Coverage + Comment/Doc Compliance (single-LLM only)

**Skip entirely if `IS_MULTI_LLM=true`.**

**Reads:** `coverage.txt`, `metrics-test-files.txt`, `metrics-source-files.txt`,
`pattern-exports-js.txt`, `pattern-jsdoc-present.txt`,
`pattern-exports-py.txt`, `pattern-docstrings-present.txt`,
`pattern-google-docstrings.txt`, `pattern-exports-cs.txt`,
`pattern-xmldoc-present.txt`

**Test coverage:** parse coverage %, identify directories with no test files,
compute test-to-source file ratio.

**Comment/Doc compliance** — evaluate based on detected stack:

- **JS/TS:** cross-reference exported symbols against JSDoc blocks. Check for
  `@param`, `@returns`, `@throws`, summary line. Flag missing or incomplete blocks.
- **Python:** cross-reference def/class lines against docstrings. Check for
  Google-format `Args:`, `Returns:`, `Raises:` sections.
- **.NET:** cross-reference public members against `///` XML doc comments. Check
  for `<summary>`, `<param>`, `<returns>`, `<exception>`.

Read up to 20 files for spot-checking in each language.

Metrics: test coverage %, test/source file ratio, exported symbol count,
doc present count, doc compliant count, overall compliance %.

**Output:** `${AUDIT_DIR}/D-test-docs.md`

When all Task calls have returned, run `/compact` before Step 6.
Surviving state: `AUDIT_DIR`, `AUDIT_TS`, `BRANCH`, `COMMIT`, `IS_MULTI_LLM`.

---

## Step 6 — Baseline diff

```bash
PREV_SUMMARY=$(ls audit-reports/*/AUDIT-SUMMARY.md 2>/dev/null \
  | sort | grep -v "${AUDIT_TS}" | tail -1)
```

If `$PREV_SUMMARY` exists, read its `## Baseline Metrics` table and produce a
`## Changes Since Last Audit` diff table:

| Metric                      | Previous | Current | Delta |
| --------------------------- | -------- | ------- | ----- |
| Critical CVEs               |          |         |       |
| High CVEs                   |          |         |       |
| Vulnerable packages         |          |         |       |
| Suspected hardcoded secrets |          |         |       |
| Silent error patterns       |          |         |       |
| Structural logical issues   |          |         |       |
| Tech debt markers           |          |         |       |
| Type bypasses               |          |         |       |
| Debug leaks (non-test)      |          |         |       |
| Lint errors                 |          |         |       |
| Test coverage %             |          |         |       |
| Comment/Doc compliance %    |          |         |       |

Legend: ▼ = decrease (improvement for debt/errors; regression for coverage/docs)
▲ = increase (improvement for coverage/docs; regression for debt/errors)

If no previous audit exists: write
`"No previous audit found — this run establishes the baseline."` as the body.

---

## Step 7 — Synthesis: AUDIT-SUMMARY.md

Read all available subagent output files and the security audit report.
Produce `${AUDIT_DIR}/AUDIT-SUMMARY.md`.

In multi-LLM mode, `D-test-docs.md` does not exist. The Test Coverage and
Comment/Doc Compliance rows in the Findings Overview table must be present but
marked to indicate the Gemini pass is required. Baseline Metrics rows for
test coverage % and doc compliance % show `pending`.

```markdown
# Project Audit — <project name>

**Branch:** <branch>
**Commit:** <hash — first 8 chars> <message>
**Date:** <YYYY-MM-DD HH:MM IST>
**Stack:** <detected stack>
**Working tree:** <clean | DIRTY — uncommitted changes present>
**Mode:** <FULL | CLAUDE PASS — Gemini pass required>
**Baseline:** <true | false>

---

## Changes Since Last Audit

<diff table, or baseline note>

---

## Findings Overview

| Domain                 | Critical | High | Medium | Low | Notes                    |
| ---------------------- | -------- | ---- | ------ | --- | ------------------------ |
| Security (OWASP)       |          |      |        |     |                          |
| Dependencies (CVE)     |          |      |        |     |                          |
| Error Handling         |          |      |        |     |                          |
| Logical Errors         |          |      |        |     |                          |
| Tech Debt              | —        | —    |        |     |                          |
| Type Safety (TS)       | —        | —    |        |     |                          |
| Test Coverage          | —        | —    | —      | —   | Run Gemini audit command |
| Comment/Doc Compliance | —        | —    | —      | —   | Run Gemini audit command |

---

## Top 10 Action Items

[Claude-scoped domains only in multi-LLM mode — Gemini pass will add its own]

1.  ...

---

## Baseline Metrics

| Metric                      | Value  |
| --------------------------- | ------ | ----------------------------------- |
| Total source files          |        |
| Total lines of code         |        |
| Test file count             |        |
| Test coverage %             | <value | pending — run Gemini audit command> |
| Critical CVEs               |        |
| High CVEs                   |        |
| Vulnerable packages         |        |
| Suspected hardcoded secrets |        |
| Silent error patterns       |        |
| Structural logical issues   |        |
| Tech debt markers           |        |
| Type bypasses               |        |
| Debug leaks (non-test)      |        |
| Lint errors                 |        |
| Comment/Doc compliance %    | <value | pending — run Gemini audit command> |

---

## Sub-reports

- [A — Dependencies & Secrets](./A-deps-secrets.md)
- [B — Error Handling & Logical Errors](./B-error-logic.md)
- [C — Tech Debt & Code Quality](./C-tech-debt.md)
- [D — Test Coverage & Documentation](./D-test-docs.md) ← Gemini pass
- [Security Audit (OWASP)](./security-audit.md)
```

The `## Report Metadata` section must appear at the end:

```markdown
## Report Metadata

- Input config: <AGENTS.md | CLAUDE.md>
- Output dir: <path>
- Baseline: <true | false>
- Mode: <FULL | CLAUDE PASS>
- Baseline: <true | false>
```

---

## Step 8 — Token usage report

Write `${AUDIT_DIR}/token-usage.md`:

```markdown
# Token Usage — <project name> audit <AUDIT_TS>

## Per-step breakdown

| Step      | Description                      | Tokens (approx)   |
| --------- | -------------------------------- | ----------------- |
| 0         | Mode detection                   |                   |
| 1         | Pre-flight checks                |                   |
| 2         | Repo state + config resolution   |                   |
| 3         | Shell subagent (all tooling)     |                   |
| 4         | Security scan (/security-audit)  |                   |
| 5A        | Subagent A — Deps + Secrets      |                   |
| 5B        | Subagent B — Error + Logic       |                   |
| 5C        | Subagent C — Tech debt + Quality |                   |
| 5D        | Subagent D — Test + Docs         | N/A (Gemini pass) |
| 6         | Baseline diff                    |                   |
| 7         | Synthesis (AUDIT-SUMMARY.md)     |                   |
| **Total** |                                  | \*\* \*\*         |

## Compaction savings

| Compaction point | Tokens in context before | Tokens after | Saved |
| ---------------- | ------------------------ | ------------ | ----- |
| After Step 1     |                          |              |       |
| After Step 2     |                          |              |       |
| After Step 4     |                          |              |       |
| After Step 5     |                          |              |       |

## Notes

- Model used (orchestrator): <model>
- Model used (subagents): <model>
- Largest single step: Step <N> — <tokens>
```

---

## Step 9 — Done

Print:

```
Audit complete.
  Summary:      audit-reports/<timestamp>/AUDIT-SUMMARY.md
  Token report: audit-reports/<timestamp>/token-usage.md
  Sub-reports:  audit-reports/<timestamp>/
```

If `IS_MULTI_LLM=true`, append:

```
Claude pass complete. Run the Gemini audit command to finish the audit:
  /project:audit-gemini
```

Do not delete any intermediate files. They are part of the audit record.
