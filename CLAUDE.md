# CLAUDE.md

## Project

Personal collection of Claude Code skills, Gemini CLI custom commands, shell scripts, and workflow documentation for LLM-assisted development. The repo serves as a portable toolkit: skills are installed to `~/.claude/skills/` (global) or `.claude/skills/` (project-local); Gemini CLI commands are distributed as TOML files; scripts are one-shot automations for GitHub project management and telemetry setup.

## Stack

- Shell (bash/zsh) — scripts and skill entry points
- Python — `claude/skills/token-usage-review/claude_token_report.py`
- Markdown — skill bodies (`SKILL.md`), documentation
- TOML — Gemini CLI custom commands
- OpenTelemetry — telemetry exporter to your team's OTEL collector (set via `OTEL_ENDPOINT`; see `scripts/setup-telemetry.sh`)
- GitHub CLI (`gh`) — project management scripts

## Architecture

```
claude/skills/     Personal Claude Code skills (copy SKILL.md to ~/.claude/skills/<name>/)
dashboard/         Shareable skills and Gemini CLI TOML commands for project teams
  <name>/SKILL.md      Claude Code skill body
  <name>/<name>.toml   Gemini CLI custom command
docs/              Workflow reference documentation
scripts/           One-shot shell scripts (telemetry setup, GitHub project management)
```

Each tool is self-contained: `README.md` covers install and verification; `SKILL.md` is the skill body Claude Code loads.

## Install pattern

```bash
# Global (personal)
mkdir -p ~/.claude/skills/<name>
cp dashboard/<name>/SKILL.md ~/.claude/skills/<name>/

# Project-local
mkdir -p .claude/skills/<name>
cp dashboard/<name>/SKILL.md .claude/skills/<name>/
```

## Conventions

- Every tool directory must contain a `README.md`.
- Skill bodies live in `SKILL.md`; Gemini CLI commands in `<name>.toml`.
- Scripts use `set -euo pipefail` and guard against macOS/Linux differences at the top.
- Telemetry project identity is declared in `.env.project` (`PROJECT_SLUG`) and `.envrc` (`OTEL_RESOURCE_ATTRIBUTES`).
- Do not add a build system, package manager, or test runner — this repo ships plain files.

## Related systems

- **Grafana / OTEL collector** — address set via `OTEL_ENDPOINT` when running `scripts/setup-telemetry.sh`; telemetry from Claude Code sessions lands here.
- **GitHub Projects** — `add-to-org-project.sh` and `duplicate-github-project.sh` require a `GH_TOKEN` with `project` scope.

## Out of scope

- Do not introduce a package manager or build pipeline.
- Do not modify `.envrc` OTEL endpoint without confirming with the team lead.
- Do not commit `.env`, `OVERRIDE.md`, or `HANDOFF.md`.

## Audit Config

- package_manager: none
- test_runner: none
- lint_cmd: none
- src_dirs: claude/skills, dashboard, docs, scripts
- exclude_dirs: .git
- docstring_style: none
