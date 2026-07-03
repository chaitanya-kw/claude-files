# repo-telemetry-setup

A Claude Code skill that creates the three telemetry configuration files needed to tag a repo with a project slug so it appears as a named project in the Grafana monitoring dashboard.

---

## Installation

```bash
mkdir -p ~/.claude/skills/repo-telemetry-setup
cp claude/skills/repo-telemetry-setup/SKILL.md ~/.claude/skills/repo-telemetry-setup/
```

No dependencies.

---

## Usage

Run from inside the repo you want to configure:

```
set up telemetry for this repo
add project tracking
configure this repo for the monitoring dashboard
add the project slug files
```

Claude Code will:

1. Derive a candidate slug from the folder name and ask you to confirm or replace it
2. Create or update the three config files with the confirmed slug
3. Check `.gitignore` and add negation entries for any telemetry files being ignored
4. Print a summary and next steps

### Files created

| File | Purpose |
| ---- | ------- |
| `.env.project` | Sets `PROJECT_SLUG` — read by the PowerShell hook on Windows |
| `.envrc` | Exports `OTEL_RESOURCE_ATTRIBUTES` via `direnv` on Linux/macOS |
| `.vscode/settings.json` | Sets `OTEL_RESOURCE_ATTRIBUTES` in the VS Code integrated terminal (all platforms) |

If `.vscode/settings.json` already exists, the three terminal env keys are merged in without touching other settings.

### After setup

- Commit and push all three files to the default branch
- Linux/macOS: run `direnv allow` once after cloning
- Keep the slug consistent — changing it later splits history in the dashboard
