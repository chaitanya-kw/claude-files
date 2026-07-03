---
name: repo-telemetry-setup
description: Set up per-repo telemetry configuration files for the Claude Code productivity monitoring stack. Use this skill when the user asks to "set up telemetry for this repo", "add project tracking", "configure this repo for the monitoring dashboard", "add the project slug files", or any similar phrase about tagging a repo so it appears in Grafana. Also trigger when the user mentions .envrc, .env.project, or OTEL_RESOURCE_ATTRIBUTES in the context of project labelling. Always use this skill for any request to initialise or configure repo-level monitoring — do not attempt it without the skill.
allowed-tools: Read Write Bash
disable-model-invocation: false
---

# Repo Telemetry Setup

Creates the three files needed to tag a repo with a project slug so it appears as a named project in the Grafana monitoring dashboard.

## Files this skill creates

| File                    | Purpose                                                                     |
| ----------------------- | --------------------------------------------------------------------------- |
| `.env.project`          | PowerShell hook on Windows — sets `PROJECT_SLUG` when `cd`ing into the repo |
| `.envrc`                | `direnv` on Linux/macOS — exports `OTEL_RESOURCE_ATTRIBUTES`                |
| `.vscode/settings.json` | VS Code integrated terminal on all platforms                                |

## Workflow

### Step 1 — Determine the slug

1. Read the current working directory name:
   ```bash
   basename "$PWD"
   ```
2. Convert it to a candidate slug: lowercase, spaces/underscores replaced with hyphens, strip any leading/trailing hyphens.
3. Present the candidate to the user:

   > The current folder is `<folder-name>`. I'll use `<candidate-slug>` as the project slug. Is that correct, or would you like a different slug?

4. Wait for confirmation or a replacement slug before creating any files.
5. Use whatever the user confirms. If they provide a different slug, use theirs verbatim (do not reformat it).

### Step 2 — Handle `.vscode/settings.json`

Before writing, check whether `.vscode/settings.json` already exists.

- **Does not exist**: create it with only the three `terminal.integrated.env.*` keys.
- **Exists**: read it, merge the three keys into the existing object (add them under the top-level object — do not nest or replace other keys), then write the merged result back.

Merging rule: if any of the three platform keys already exist, replace their value. Do not touch any other keys.

### Step 3 — Create the files

With the confirmed slug, create or update:

**`.env.project`** (repo root):

```
PROJECT_SLUG=<slug>
```

**`.envrc`** (repo root):

```bash
export OTEL_RESOURCE_ATTRIBUTES="project=<slug>"
```

**`.vscode/settings.json`** (create directory if absent):

```json
{
  "terminal.integrated.env.windows": {
    "OTEL_RESOURCE_ATTRIBUTES": "project=<slug>"
  },
  "terminal.integrated.env.linux": {
    "OTEL_RESOURCE_ATTRIBUTES": "project=<slug>"
  },
  "terminal.integrated.env.osx": {
    "OTEL_RESOURCE_ATTRIBUTES": "project=<slug>"
  }
}
```

### Step 4 — Check `.gitignore`

Check whether a `.gitignore` exists at the repo root. If it does, scan it for any patterns that would cause git to ignore the three telemetry files. The patterns to watch for include but are not limited to:

```
.env*
.env.project
.envrc
.vscode/
.vscode/settings.json
```

For each file, run a quick check:

```bash
git check-ignore -v .env.project .envrc .vscode/settings.json
```

Any file that git reports as ignored must be explicitly negated. Add negation entries to `.gitignore` grouped under a clear comment — insert them at the end of the file, or immediately after the pattern that caused the match if that is cleaner:

```
# Telemetry config — must be committed for dashboard project tagging
!.env.project
!.envrc
!.vscode/settings.json
```

Only add negations for files that are actually being ignored. Do not add negations preemptively.

If `.gitignore` does not exist or none of the files are ignored, skip this step silently.

### Step 5 — Confirm and remind

After writing all files, print a summary. If `.gitignore` was modified, include it in the list:

```
Created/updated:
  .env.project           PROJECT_SLUG=<slug>
  .envrc                 OTEL_RESOURCE_ATTRIBUTES="project=<slug>"
  .vscode/settings.json  terminal.integrated.env.{windows,linux,osx}
  .gitignore             added negations for telemetry files  ← only if modified

Next steps:
  - Commit and push these files to the default branch.
  - Developers on Linux/macOS must run `direnv allow` once after cloning.
  - The slug is now <slug> — keep it consistent; changing it later splits history in the dashboard.
```

## Edge cases

- **Monorepo / nested project**: The folder name heuristic may not be right. Always confirm with the user.
- **Slug with uppercase or spaces**: Normalise the candidate but never normalise what the user explicitly provides.
- **`.vscode/settings.json` is not valid JSON**: Warn the user, show the existing content, and ask how to proceed before modifying.
- **Read-only files**: If a file cannot be written, report the error and stop rather than silently skipping.
