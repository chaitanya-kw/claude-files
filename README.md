# claude-files

A personal collection of tools, slash commands, configurations and docs for LLM workflows.

Started out for Claude Code and ever expanding to infinity and beyond.

Each file or tool has its own README.

---

## Skills

| Skill | Location | Description |
| ----- | -------- | ----------- |
| `init-claude-md` | `dashboard/init-claude-md/` | Audit a project and produce a `CLAUDE.md` (or `AGENTS.md` + `CLAUDE.md` for multi-LLM projects) |
| `progress-review` | `dashboard/progress-review/` | Review project progress against a GitHub Project V2 |
| `project-audit` | `dashboard/project-audit/` | Run a multi-dimensional code audit (Claude pass) |
| `repo-telemetry-setup` | `claude/skills/repo-telemetry-setup/` | Configure per-repo telemetry for the Claude Code monitoring stack |
| `token-usage-review` | `claude/skills/token-usage-review/` | Analyse Claude Code token usage from session files |
| `weekly-status-report` | `claude/skills/weekly-status-report/` | Generate a weekly status report for any GitHub Project V2 |
| `snm-tnm-monthly-report-generator` | `claude/skills/snm-tnm-monthly-report-generator/` | Generate a branded Kilowott monthly S&M/T&M client report as a self-contained HTML file |
| `project-instructions-creator` | `claude/skills/project-instructions-creator/` | Create Claude Project instructions for a new engagement |

---

## Installation

### Claude Code skills (personal — available in all projects)

```bash
mkdir -p ~/.claude/skills/<name>
cp claude/skills/<name>/SKILL.md ~/.claude/skills/<name>/
# If the skill has supplementary files, copy the whole directory:
cp -r claude/skills/<name> ~/.claude/skills/
```

### Claude Code skills (project-local)

```bash
mkdir -p .claude/skills/<name>
cp claude/skills/<name>/SKILL.md .claude/skills/<name>/
```

See each tool's `README.md` for full install steps and verification.
